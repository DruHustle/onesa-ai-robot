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
from fastapi.security import HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from robot_api.edge import EdgeMonitor, Telemetry
from robot_api.safety import Proposal, SafetyGate, SafetyViolation
from robot_api.security import PasswordVerifier, VerificationBusy, token_hash
from robot_api.turso import COLUMNS, TursoJournal, endpoint

REQUEST_BODY_SECONDS = 5


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ROBOT_", extra="ignore", hide_input_in_errors=True
    )
    public_origin: str = "http://localhost:3431"
    operator_name: str = Field(default="operator", min_length=1, max_length=64)
    operator_password_hash: str
    database_path: Path = Path("storage/robot.sqlite3")
    edge_device_id: str = ""
    edge_token_sha256: str = ""
    actuation_enabled: bool = False
    deployment_environment: Literal["local", "staging", "production"] = "local"
    storage_mode: Literal["persistent", "ephemeral-simulation", "turso"] = "persistent"
    turso_database_url: str = ""
    turso_auth_token: SecretStr = SecretStr("")
    session_seconds: int = Field(default=900, ge=60, le=3600)
    heartbeat_seconds: float = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def safe_runtime(self):
        from urllib.parse import urlsplit

        url = urlsplit(self.public_origin)
        if bool(self.edge_device_id) != bool(self.edge_token_sha256):
            raise ValueError("Configure both synthetic edge identity and token hash")
        if self.edge_device_id:
            import re

            if not re.fullmatch(
                r"synthetic-[a-z0-9-]{1,48}", self.edge_device_id
            ) or not re.fullmatch(r"[a-f0-9]{64}", self.edge_token_sha256):
                raise ValueError("Only authenticated synthetic telemetry devices are supported")
        if self.deployment_environment == "production" and self.storage_mode != "persistent":
            raise ValueError("Production requires approved persistent simulation storage")
        if self.storage_mode == "turso":
            if self.deployment_environment != "staging":
                raise ValueError("Remote task journal is currently qualified for staging only")
            endpoint(self.turso_database_url)
            token = self.turso_auth_token.get_secret_value()
            if not token or len(token) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in token):
                raise ValueError("Configure a database-scoped Turso auth token")
        elif self.turso_database_url or self.turso_auth_token.get_secret_value():
            raise ValueError("Select turso storage explicitly; remote settings cannot be ignored")
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
    edge_telemetry: Literal["simulation_connected", "not_connected"] = "not_connected"
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
        self.journal = (
            TursoJournal(settings.turso_database_url, settings.turso_auth_token)
            if settings.storage_mode == "turso"
            else None
        )
        self.journal_dirty: dict[str, int] = {}
        self.journal_version = 0
        self.journal_lock = asyncio.Lock()
        self.journal_failed = False
        self.journal_lease_confirmed_at = 0.0
        self.stop_epoch = 0
        self.mutation_lock = asyncio.Lock()
        if not self.journal:
            settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        # Transactions, routes and watchdog run on one application event-loop thread.
        # Reject foreign-thread access rather than sharing an implicit transaction.
        self.db = sqlite3.connect(":memory:" if self.journal else settings.database_path, timeout=2)
        self.db.row_factory = sqlite3.Row
        if not self.journal:
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

    async def initialize_journal(self) -> None:
        if not self.journal:
            return
        rows = await self.journal.initialize()
        self.journal_lease_confirmed_at = time.monotonic()
        self.db.executemany(
            f"INSERT INTO tasks({','.join(COLUMNS)}) VALUES(?,?,?,?,?,?,?)",
            [tuple(row[col] for col in COLUMNS) for row in rows],
        )
        self.db.commit()
        # Restore history only, never operator sessions or execution authority.
        self.cancel("process_restart", stop=True)
        await self.flush_journal()
        await self.refresh_journal_lease()

    async def refresh_journal_lease(self) -> None:
        if not self.journal or self.journal_failed:
            raise sqlite3.OperationalError("Remote simulation journal requires recovery")
        try:
            await self.journal.renew()
            self.journal_lease_confirmed_at = time.monotonic()
        except sqlite3.Error:
            self.fail_journal()
            raise

    def dirty(self, task_id: str) -> None:
        if self.journal:
            self.journal_version += 1
            self.journal_dirty[task_id] = self.journal_version

    def fail_journal(self) -> None:
        self.journal_failed = True
        self.cancel("storage_unavailable", stop=True)

    async def flush_journal(self) -> None:
        if not self.journal:
            return
        if self.journal_failed:
            raise sqlite3.OperationalError("Remote simulation journal requires recovery")
        async with self.journal_lock:
            if self.journal_failed:
                raise sqlite3.OperationalError("Remote simulation journal requires recovery")
            try:
                # Versions prevent a pending running write from clearing a later stop.
                while self.journal_dirty:
                    task_id, version = next(iter(self.journal_dirty.items()))
                    row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
                    await self.journal.save(dict(row))
                    if self.journal_dirty.get(task_id) == version:
                        self.journal_dirty.pop(task_id)
            except sqlite3.Error:
                self.fail_journal()
                raise

    @property
    def stopped(self) -> bool:
        return bool(self.db.execute("SELECT stopped FROM safety WHERE id=1").fetchone()[0])

    def cancel(self, reason: str, stop: bool = False) -> None:
        self.active = None
        for row in self.db.execute("SELECT id FROM tasks WHERE state IN ('running','proposed')"):
            self.dirty(row[0])
        self.db.execute(
            "UPDATE tasks SET state='cancelled',reason=? WHERE state IN ('running','proposed')",
            (reason,),
        )
        if stop:
            self.stop_epoch += 1
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
            self.dirty(active["id"])
            self.active = None


Session = dict[str, str]


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        state = State(config)
        try:
            await state.initialize_journal()
        except BaseException:
            state.db.close()
            if state.journal:
                await state.journal.close()
            raise
        app.state.sim = state
        app.state.edge = EdgeMonitor(config.edge_device_id, config.edge_token_sha256)
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

        async def journal_watch():
            # Cloud writes occur on events, not on the 20 Hz simulation loop.
            renewed = time.monotonic()
            while True:
                await asyncio.sleep(0.1)
                try:
                    await state.flush_journal()
                    if state.journal and time.monotonic() - renewed >= 10:
                        await state.refresh_journal_lease()
                        renewed = time.monotonic()
                except sqlite3.Error:
                    state.fail_journal()
                    return  # Bounded fail-closed; operator recovery requires restart.

        journal_task = asyncio.create_task(journal_watch()) if state.journal else None
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
                    if journal_task:
                        journal_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await journal_task
                    state.cancel("process_shutdown", stop=True)
                    with contextlib.suppress(sqlite3.Error):
                        await state.flush_journal()
                finally:
                    state.db.close()
                    if state.journal:
                        await state.journal.close()

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
            if (
                request.url.path != "/api/v1/edge/telemetry"
                and request.headers.get("origin") != config.public_origin
            ):
                return Response(status_code=403)
            body = b""
            try:
                # A total deadline also bounds a client that keeps trickling bytes.
                async with asyncio.timeout(REQUEST_BODY_SECONDS):
                    async for chunk in request.stream():
                        if len(body) + len(chunk) > 16384:
                            return Response(status_code=413, headers={"Cache-Control": "no-store"})
                        body += chunk
            except TimeoutError:
                return Response(status_code=408, headers={"Cache-Control": "no-store"})
            request._body = body
        try:
            sim = request.app.state.sim
            if sim.journal and request.method not in ("GET", "HEAD", "OPTIONS"):
                # Serialize operator mutations across acknowledgement yields. Stop
                # and heartbeat are exempt so cloud latency cannot delay local safety.
                if request.url.path in (
                    "/api/v1/stop",
                    "/api/v1/heartbeat",
                    "/api/v1/auth/logout",
                ) or request.url.path.endswith("/cancel"):
                    response = await call_next(request)
                    await sim.flush_journal()
                else:
                    async with sim.mutation_lock:
                        if sim.journal_failed:
                            raise sqlite3.OperationalError("Remote journal unavailable")
                        response = await call_next(request)
                        await sim.flush_journal()
            else:
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
        sim = request.app.state.sim
        if request.app.state.watch.done():
            if sim.active:
                sim.cancel("watchdog_failure", stop=True)
            if require_watchdog:
                raise HTTPException(503, "Safety watchdog unavailable")
        # Enforce expired authority before a late heartbeat can refresh it, even
        # when the background tick was delayed by event-loop scheduling.
        sim.tick()
        return sim

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

    async def session(request: Request) -> Session:
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

    @app.get("/api/v1/edge/challenge", dependencies=[Depends(HTTPBearer(auto_error=False))])
    async def edge_challenge(request: Request):
        monitor = request.app.state.edge
        monitor.authorize(request.headers.get("authorization", ""))
        return {
            "boot_challenge": monitor.challenge,
            "next_sequence": monitor.sequence + 1,
            "version": 1,
        }

    @app.post("/api/v1/edge/telemetry", dependencies=[Depends(HTTPBearer(auto_error=False))])
    async def edge_telemetry(value: Telemetry, request: Request):
        monitor = request.app.state.edge
        monitor.authorize(request.headers.get("authorization", ""))
        monitor.receive(value)
        return {"status": "received", "scope": "simulation-telemetry-only"}

    @app.get("/api/v1/edge/audit")
    async def edge_audit(request: Request, operator: Operator):
        return {"events": list(request.app.state.edge.audit), "retention": "bounded-process-memory"}

    @app.get("/api/v1/health")
    def health():
        return {"status": "live", "mode": "simulation"}

    @app.get("/api/v1/ready")
    async def ready(request: Request):
        sim = state(request)
        if request.app.state.watch.done():
            raise HTTPException(503, "Safety watchdog unavailable")
        if sim.journal:
            if sim.journal_failed:
                raise HTTPException(503, "Remote simulation journal requires recovery")
            # Anonymous health traffic must not consume remote connections. The
            # background lease renewal supplies a bounded, real database proof.
            if time.monotonic() - sim.journal_lease_confirmed_at > 15:
                sim.fail_journal()
                raise HTTPException(503, "Remote simulation journal lease check expired")
        if sim.db.execute("SELECT count(*) FROM safety WHERE id=1").fetchone()[0] != 1:
            raise HTTPException(503, "Safety state unavailable")
        return {
            "status": "ready",
            "mode": "simulation",
            "physical_actuation": False,
            "storage_mode": config.storage_mode,
            "deployment_environment": config.deployment_environment,
        }

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
                "edge_telemetry": request.app.state.edge.status(),
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
        sim = state(request)
        await sim.flush_journal()
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
        if sim.journal_failed:
            raise HTTPException(503, "Remote simulation journal requires recovery")
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
            sim.dirty(str(value.command_id))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Command ID already used") from None
        return {"id": str(value.command_id), "state": "proposed"}

    @app.post("/api/v1/tasks/{task_id}/approve", response_model=TaskResponse)
    async def approve(task_id: str, value: Confirmation, request: Request, operator: Operator):
        sim = state(request, require_watchdog=True)
        await confirm(sim, request, value.password)
        # Confirmation yields to the watchdog/logout; recheck authority afterwards.
        sim = state(request, require_watchdog=True)
        operator = await session(request)
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
        sim.db.execute(
            "UPDATE tasks SET state='running',reason='operator_approved' WHERE id=?", (task_id,)
        )
        sim.db.commit()
        sim.dirty(task_id)
        await sim.flush_journal()
        sim = state(request, require_watchdog=True)
        try:
            await session(request)
        except HTTPException:
            sim.cancel("approval_authority_lost", stop=True)
            await sim.flush_journal()
            raise
        if sim.stopped or sim.active:
            sim.cancel("approval_authority_lost", stop=True)
            await sim.flush_journal()
            raise HTTPException(409, "Stopped or already running")
        try:
            sim.gate.validate(proposal, sim.position)
        except SafetyViolation:
            sim.cancel("approval_expired", stop=True)
            await sim.flush_journal()
            raise HTTPException(409, "Proposal expired during storage acknowledgement") from None
        sim.active = {
            "id": task_id,
            "session": operator["token"],
            "proposal": proposal,
            "start": sim.position,
            "started": time.monotonic(),
            "heartbeat": time.monotonic(),
        }
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
        if row["state"] == "running" or (sim.active and sim.active["id"] == task_id):
            sim.cancel("operator_cancel", stop=True)
        else:
            sim.db.execute(
                "UPDATE tasks SET state='cancelled',reason='operator_cancel' "
                "WHERE id=? AND state='proposed'",
                (task_id,),
            )
            sim.db.commit()
            sim.dirty(task_id)
        return {"status": "cancelled"}

    @app.post("/api/v1/stop", response_model=ActionResponse)
    async def stop(request: Request, operator: Operator):
        state(request).cancel("operator_stop", stop=True)
        return {"status": "stopped"}

    @app.post("/api/v1/reset", response_model=ActionResponse)
    async def reset(value: Confirmation, request: Request, operator: Operator):
        sim = state(request, require_watchdog=True)
        stop_epoch = sim.stop_epoch
        await confirm(sim, request, value.password)
        sim = state(request, require_watchdog=True)
        await session(request)
        if sim.journal_failed:
            raise HTTPException(503, "Remote simulation journal requires recovery")
        if sim.stop_epoch != stop_epoch:
            raise HTTPException(409, "Stop changed during reset confirmation")
        if sim.active:
            raise HTTPException(409, "Cancel the current task first")
        sim.db.execute("UPDATE safety SET stopped=0 WHERE id=1")
        sim.db.commit()
        return {"status": "reset", "physical_actuation": False}

    return app
