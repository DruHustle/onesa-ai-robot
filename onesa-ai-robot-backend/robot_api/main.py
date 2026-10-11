"""Authenticated, persistent software simulator. Physical operation is unavailable."""

import asyncio
import contextlib
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from robot_api.safety import Proposal, SafetyGate, SafetyViolation
from robot_api.security import PasswordVerifier, VerificationBusy, token_hash


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ROBOT_", extra="ignore", hide_input_in_errors=True
    )
    public_origin: str = "http://localhost:3431"
    operator_name: str = Field(default="operator", min_length=1, max_length=64)
    operator_password_hash: str
    database_path: Path = Path("storage/robot.sqlite3")
    actuation_enabled: bool = False
    session_seconds: int = Field(default=900, ge=60, le=3600)
    heartbeat_seconds: float = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def safe_runtime(self):
        from urllib.parse import urlsplit

        url = urlsplit(self.public_origin)
        if self.actuation_enabled:
            raise ValueError("Physical actuation is not implemented or authorized")
        if (
            url.scheme not in ("http", "https")
            or not url.netloc
            or url.path not in ("", "/")
            or url.query
            or url.fragment
            or url.username
            or url.password
        ):
            raise ValueError("Set an exact HTTP(S) public origin")
        if url.scheme == "http" and url.hostname not in ("localhost", "127.0.0.1"):
            raise ValueError("Remote operator access requires HTTPS")
        self.public_origin = self.public_origin.rstrip("/")
        if (
            not self.operator_password_hash.startswith("scrypt$")
            or len(self.operator_password_hash.split("$")) != 3
        ):
            raise ValueError("Configure a generated operator password hash")
        _, salt, digest = self.operator_password_hash.split("$")
        if (
            len(salt) != 32
            or len(digest) != 128
            or any(c not in "0123456789abcdef" for c in salt + digest)
        ):
            raise ValueError("Invalid operator password hash")
        return self


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    csrf: str
    name: str


class Capabilities(BaseModel):
    ros2: Literal["not_connected"] = "not_connected"
    camera: Literal["not_connected"] = "not_connected"
    stt: Literal["not_configured"] = "not_configured"
    vlm: Literal["not_configured"] = "not_configured"
    tts: Literal["not_configured"] = "not_configured"
    vla: Literal["not_configured"] = "not_configured"


class StatusResponse(BaseModel):
    mode: Literal["simulation"]
    physical_actuation: Literal[False]
    stopped: bool
    position_radians: float
    operator: str
    active_task: str | None
    capabilities: Capabilities


class TaskSummary(BaseModel):
    id: str
    state: Literal["proposed", "running", "completed", "cancelled"]
    reason: str
    created: float
    position: float


class TaskList(BaseModel):
    tasks: list[TaskSummary]


class TaskResponse(BaseModel):
    id: str
    state: Literal["proposed", "running"]


class ActionResponse(BaseModel):
    status: str
    physical_actuation: Literal[False] = False


class State:
    def __init__(self, settings: Settings):
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(settings.database_path, check_same_thread=False, timeout=2)
        self.db.row_factory = sqlite3.Row
        settings.database_path.chmod(0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, csrf TEXT, expires REAL, name TEXT);
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, owner TEXT, proposal TEXT, state TEXT,
                reason TEXT, created REAL, position REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS safety (
                id INTEGER PRIMARY KEY CHECK(id=1), stopped INTEGER NOT NULL);
            INSERT OR IGNORE INTO safety VALUES(1,1);
        """)
        # Process restart never resumes a command or retains execution authority.
        self.db.execute("DELETE FROM sessions")
        self.db.execute("UPDATE safety SET stopped=1 WHERE id=1")
        self.db.execute(
            "UPDATE tasks SET state='cancelled',reason='process_restart' "
            "WHERE state IN ('proposed','running')"
        )
        self.db.commit()
        self.settings, self.gate = settings, SafetyGate()
        self.active: dict | None = None
        self.position = 0.0
        self.failures: dict[str, deque] = defaultdict(deque)

    @property
    def stopped(self) -> bool:
        return bool(self.db.execute("SELECT stopped FROM safety WHERE id=1").fetchone()[0])

    def cancel(self, reason: str, stop: bool = False) -> None:
        self.active = None
        self.db.execute(
            "UPDATE tasks SET state='cancelled',reason=? WHERE state IN ('running','proposed')",
            (reason,),
        )
        if stop:
            self.db.execute("UPDATE safety SET stopped=1 WHERE id=1")
        self.db.commit()
        self.active = None

    def tick(self) -> None:
        active = self.active
        if not active:
            return
        session = self.db.execute(
            "SELECT expires FROM sessions WHERE token=?", (active["session"],)
        ).fetchone()
        if (
            self.stopped
            or session is None
            or session[0] <= time.time()
            or time.monotonic() - active["heartbeat"] > self.settings.heartbeat_seconds
        ):
            self.cancel("operator_connection_lost", stop=True)
            return
        proposal = active["proposal"]
        try:
            self.position, _, _ = self.gate.sample(
                active["start"],
                proposal.target_radians,
                proposal.duration_seconds,
                time.monotonic() - active["started"],
            )
        except SafetyViolation:
            self.cancel("safety_gate", stop=True)
            return
        completed = time.monotonic() - active["started"] >= proposal.duration_seconds
        self.db.execute(
            "UPDATE tasks SET state=?,position=? WHERE id=?",
            ("completed" if completed else "running", self.position, active["id"]),
        )
        self.db.commit()
        if completed:
            self.active = None


Session = dict[str, str]


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        state = State(config)
        app.state.sim = state
        app.state.passwords = PasswordVerifier()

        async def watch():
            while True:
                await asyncio.sleep(0.05)
                try:
                    state.tick()
                except (sqlite3.Error, SafetyViolation):
                    state.active = None
                    with contextlib.suppress(sqlite3.Error):
                        state.cancel("watchdog_failure", stop=True)
                    raise

        task = asyncio.create_task(watch())
        app.state.watch = task
        try:
            yield
        finally:
            try:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            finally:
                try:
                    state.cancel("process_shutdown", stop=True)
                finally:
                    state.db.close()

    app = FastAPI(
        title="Onesa Robot Simulation API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("origin") != config.public_origin:
                return Response(status_code=403)
            body = b""
            async for chunk in request.stream():
                body += chunk
                if len(body) > 16384:
                    return Response(status_code=413)
            request._body = body
        try:
            response = await call_next(request)
        except sqlite3.Error:
            response = Response(status_code=503)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            }
        )
        return response

    def state(request: Request, require_watchdog: bool = False) -> State:
        if require_watchdog and request.app.state.watch.done():
            raise HTTPException(503, "Safety watchdog unavailable")
        return request.app.state.sim

    async def password_valid(request: Request, password: str) -> bool:
        try:
            return await request.app.state.passwords.verify(password, config.operator_password_hash)
        except VerificationBusy:
            raise HTTPException(429, "Password verification busy; retry later") from None

    async def confirm(sim: State, request: Request, password: str) -> None:
        failures = sim.failures["confirmation"]
        while failures and failures[0] < time.monotonic() - 60:
            failures.popleft()
        if len(failures) >= 5:
            raise HTTPException(429, "Confirmation attempts exceeded")
        if not await password_valid(request, password):
            failures.append(time.monotonic())
            raise HTTPException(403, "Operator confirmation required")

    def session(request: Request) -> Session:
        sim = state(request)
        key = token_hash(request.cookies.get("robot_session", ""))
        row = sim.db.execute(
            "SELECT * FROM sessions WHERE token=? AND expires>?", (key, time.time())
        ).fetchone()
        if row is None:
            raise HTTPException(401, "Sign in required")
        if request.method != "GET" and not secrets.compare_digest(
            request.headers.get("x-csrf-token", ""), row["csrf"]
        ):
            raise HTTPException(403, "CSRF verification failed")
        return dict(row)

    Operator = Annotated[Session, Depends(session)]

    @app.get("/api/v1/health")
    def health():
        return {"status": "live", "mode": "simulation"}

    @app.get("/api/v1/ready")
    async def ready(request: Request):
        sim = state(request)
        if request.app.state.watch.done():
            raise HTTPException(503, "Safety watchdog unavailable")
        if sim.db.execute("SELECT count(*) FROM safety WHERE id=1").fetchone()[0] != 1:
            raise HTTPException(503, "Safety state unavailable")
        return {"status": "ready", "mode": "simulation", "physical_actuation": False}

    @app.post("/api/v1/auth/login", response_model=SessionResponse)
    async def login(value: Login, request: Request, response: Response):
        sim = state(request)
        # No forwarded header trust. A single configured operator; failures are global
        # as well as per network peer, preventing spoofed peer/rate-limit bypass.
        failures = sim.failures["operator"]
        while failures and failures[0] < time.monotonic() - 60:
            failures.popleft()
        if len(failures) >= 5:
            raise HTTPException(429, "Try again later")
        valid = await password_valid(request, value.password)
        if value.name != config.operator_name or not valid:
            failures.append(time.monotonic())
            raise HTTPException(401, "Invalid credentials")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        sim.db.execute("DELETE FROM sessions WHERE expires<=?", (time.time(),))
        if sim.db.execute("SELECT count(*) FROM sessions").fetchone()[0] >= 10:
            raise HTTPException(429, "Session limit reached")
        sim.db.execute(
            "INSERT INTO sessions VALUES(?,?,?,?)",
            (token_hash(token), csrf, time.time() + config.session_seconds, value.name),
        )
        sim.db.commit()
        response.set_cookie(
            "robot_session",
            token,
            max_age=config.session_seconds,
            httponly=True,
            secure=config.public_origin.startswith("https:"),
            samesite="strict",
            path="/api/v1",
        )
        return {"csrf": csrf, "name": value.name}

    @app.get("/api/v1/auth/me", response_model=SessionResponse)
    async def me(operator: Operator):
        return {"csrf": operator["csrf"], "name": operator["name"]}

    @app.post("/api/v1/auth/logout", response_model=ActionResponse)
    async def logout(request: Request, response: Response, operator: Operator):
        sim = state(request)
        if sim.active and sim.active["session"] == operator["token"]:
            sim.cancel("session_revoked", stop=True)
        sim.db.execute("DELETE FROM sessions WHERE token=?", (operator["token"],))
        sim.db.commit()
        response.delete_cookie("robot_session", path="/api/v1")
        return {"status": "signed_out"}

    @app.get("/api/v1/status", response_model=StatusResponse)
    async def status(request: Request, operator: Operator):
        sim = state(request)
        return {
            "mode": "simulation",
            "physical_actuation": False,
            "stopped": sim.stopped,
            "position_radians": sim.position,
            "operator": operator["name"],
            "active_task": sim.active["id"] if sim.active else None,
            "capabilities": {
                "ros2": "not_connected",
                "camera": "not_connected",
                "stt": "not_configured",
                "vlm": "not_configured",
                "tts": "not_configured",
                "vla": "not_configured",
            },
        }

    @app.get("/api/v1/tasks", response_model=TaskList)
    async def tasks(request: Request, operator: Operator):
        rows = (
            state(request)
            .db.execute(
                "SELECT id,state,reason,created,position FROM tasks WHERE owner=? "
                "ORDER BY created DESC LIMIT 50",
                (operator["name"],),
            )
            .fetchall()
        )
        return {"tasks": [dict(row) for row in rows]}

    @app.post("/api/v1/tasks", status_code=201, response_model=TaskResponse)
    async def propose(value: Proposal, request: Request, operator: Operator):
        sim = state(request, require_watchdog=True)
        if sim.stopped:
            raise HTTPException(409, "Reset the simulation stop state first")
        try:
            sim.gate.validate(value, sim.position)
        except SafetyViolation as exc:
            raise HTTPException(422, str(exc)) from None
        if sim.db.execute("SELECT count(*) FROM tasks").fetchone()[0] >= 10000:
            raise HTTPException(429, "History capacity reached; operator retention review required")
        if sim.db.execute("SELECT count(*) FROM tasks WHERE state='proposed'").fetchone()[0] >= 5:
            raise HTTPException(429, "Pending proposal limit reached")
        try:
            sim.db.execute(
                "INSERT INTO tasks(id,owner,proposal,state,reason,created) "
                "VALUES(?,?,?,'proposed','awaiting_operator',?)",
                (str(value.command_id), operator["name"], value.model_dump_json(), time.time()),
            )
            sim.db.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Command ID already used") from None
        return {"id": str(value.command_id), "state": "proposed"}

    @app.post("/api/v1/tasks/{task_id}/approve", response_model=TaskResponse)
    async def approve(task_id: str, value: Confirmation, request: Request, operator: Operator):
        sim = state(request, require_watchdog=True)
        await confirm(sim, request, value.password)
        # Confirmation yields to the watchdog/logout; recheck authority afterwards.
        sim = state(request, require_watchdog=True)
        operator = session(request)
        if sim.stopped or sim.active:
            raise HTTPException(409, "Stopped or already running")
        row = sim.db.execute(
            "SELECT * FROM tasks WHERE id=? AND owner=?", (task_id, operator["name"])
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Task not found")
        if row["state"] != "proposed":
            raise HTTPException(409, "Task cannot be replayed")
        proposal = Proposal.model_validate_json(row["proposal"])
        try:
            sim.gate.validate(proposal, sim.position)
        except SafetyViolation as exc:
            raise HTTPException(422, str(exc)) from None
        sim.active = {
            "id": task_id,
            "session": operator["token"],
            "proposal": proposal,
            "start": sim.position,
            "started": time.monotonic(),
            "heartbeat": time.monotonic(),
        }
        sim.db.execute(
            "UPDATE tasks SET state='running',reason='operator_approved' WHERE id=?", (task_id,)
        )
        sim.db.commit()
        return {"id": task_id, "state": "running"}

    @app.post("/api/v1/heartbeat", response_model=ActionResponse)
    async def heartbeat(request: Request, operator: Operator):
        sim = state(request)
        if sim.active and sim.active["session"] == operator["token"]:
            sim.active["heartbeat"] = time.monotonic()
        return {"status": "received"}

    @app.post("/api/v1/tasks/{task_id}/cancel", response_model=ActionResponse)
    async def cancel(task_id: str, request: Request, operator: Operator):
        sim = state(request)
        row = sim.db.execute(
            "SELECT * FROM tasks WHERE id=? AND owner=?", (task_id, operator["name"])
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Task not found")
        if sim.active and sim.active["id"] == task_id:
            sim.cancel("operator_cancel", stop=True)
        else:
            sim.db.execute(
                "UPDATE tasks SET state='cancelled',reason='operator_cancel' "
                "WHERE id=? AND state='proposed'",
                (task_id,),
            )
            sim.db.commit()
        return {"status": "cancelled"}

    @app.post("/api/v1/stop", response_model=ActionResponse)
    async def stop(request: Request, operator: Operator):
        state(request).cancel("operator_stop", stop=True)
        return {"status": "stopped"}

    @app.post("/api/v1/reset", response_model=ActionResponse)
    async def reset(value: Confirmation, request: Request, operator: Operator):
        sim = state(request, require_watchdog=True)
        await confirm(sim, request, value.password)
        sim = state(request, require_watchdog=True)
        session(request)
        if sim.active:
            raise HTTPException(409, "Cancel the current task first")
        sim.db.execute("UPDATE safety SET stopped=0 WHERE id=1")
        sim.db.commit()
        return {"status": "reset", "physical_actuation": False}

    return app
