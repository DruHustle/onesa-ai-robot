"""Bounded remote task journal; operator authority and watchdog remain process-local."""

import asyncio
import json
import math
import re
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

TABLE = "robot_simulation_tasks_v1"
LEASE = "robot_simulation_lease_v1"
PRODUCTION_DATABASE = "libsql://onesa-ai-robot-backend-druhustle.aws-eu-west-1.turso.io"
COLUMNS = ("id", "owner", "proposal", "state", "reason", "created", "position")
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
DIAGNOSTIC_CATEGORIES = frozenset(
    {
        "timeout",
        "transport",
        "http_status",
        "protocol",
        "ownership",
        "schema",
        "capacity",
        "sqlite",
        "startup_deadline",
        "lease_stale",
        "unknown",
    }
)
DIAGNOSTIC_PHASES = frozenset(
    {
        "query",
        "lease_schema",
        "lease_acquire",
        "history_schema",
        "history_read",
        "history_validate",
        "task_save",
        "task_save_reconcile",
        "lease_renew",
        "lease_probe",
        "lease_release",
        "initialize",
        "flush",
        "ready",
        "unknown",
    }
)


class JournalFailure(sqlite3.OperationalError):
    """Fixed diagnostic metadata; never copy exception or provider contents."""

    def __init__(self, category: str, phase: str, elapsed_ms: int = 0, http_status: int = 0):
        messages = {
            "ownership": "Simulation journal ownership expired",
            "capacity": "Simulation history capacity exceeded",
            "schema": "Invalid simulation journal schema or history",
        }
        super().__init__(messages.get(category, "Remote simulation journal unavailable"))
        self.category = category if category in DIAGNOSTIC_CATEGORIES else "unknown"
        self.phase = phase if phase in DIAGNOSTIC_PHASES else "unknown"
        self.elapsed_ms = min(120_000, max(0, elapsed_ms)) if type(elapsed_ms) is int else 0
        self.http_status = (
            http_status if type(http_status) is int and 100 <= http_status <= 599 else 0
        )


def endpoint(value: str) -> str:
    url = urlsplit(value)
    if (
        url.scheme != "libsql"
        or not url.hostname
        or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.turso\.io", url.hostname)
        or url.username
        or url.password
        or url.port
        or url.path not in ("", "/")
        or url.query
        or url.fragment
    ):
        raise ValueError("Set a credential-free libsql:// Turso database origin")
    return f"https://{url.hostname}/v2/pipeline"


class JournalAlreadyOwned(sqlite3.OperationalError):
    """A healthy prior instance retains the exclusive simulation lease."""


class TursoJournal:
    def __init__(self, url: str, token: SecretStr):
        self.owner = secrets.token_hex(16)
        self.url = endpoint(url)
        self.client = httpx.AsyncClient(
            headers={"Authorization": "Bearer " + token.get_secret_value()},
            timeout=1.0,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=1),
            follow_redirects=False,
            trust_env=False,
        )

    async def execute(self, sql: str, args: tuple = (), *, phase: str = "query") -> list[dict]:
        # No implicit retries: a timeout may follow a committed write.
        def encode(value):
            if value is None:
                return {"type": "null"}
            if isinstance(value, int):
                return {"type": "integer", "value": str(value)}
            if isinstance(value, float) and math.isfinite(value):
                return {"type": "float", "value": value}
            if isinstance(value, str):
                return {"type": "text", "value": value}
            raise ValueError("Unsupported journal parameter")

        body = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql, "args": [encode(v) for v in args]}},
                {"type": "close"},
            ]
        }
        started = time.monotonic()
        try:
            async with asyncio.timeout(2):
                async with self.client.stream("POST", self.url, json=body) as response:
                    response.raise_for_status()
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(payload) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise ValueError("Journal response too large")
                        payload.extend(chunk)
            results = json.loads(payload)["results"]
            if len(results) != 2 or any(result["type"] != "ok" for result in results):
                raise ValueError("Journal statement failed")
            if results[1]["response"]["type"] != "close":
                raise ValueError("Journal connection did not close")
            result = results[0]["response"]
            if result["type"] != "execute":
                raise ValueError("Invalid journal response")
            columns = [col["name"] for col in result["result"]["cols"]]
            rows = []
            for row in result["result"]["rows"]:
                values: list[str | int | float | None] = []
                for cell in row:
                    kind = cell["type"]
                    value = cell.get("value")
                    if kind == "null":
                        values.append(None)
                    elif kind == "integer":
                        values.append(int(value))
                    elif kind == "float":
                        number = float(value)
                        if not math.isfinite(number):
                            raise ValueError("Invalid journal number")
                        values.append(number)
                    elif kind == "text" and isinstance(value, str):
                        values.append(value)
                    else:
                        raise ValueError("Unsupported journal cell")
                rows.append(dict(zip(columns, values, strict=True)))
            return rows
        except (
            httpx.HTTPError,
            TimeoutError,
            ValueError,
            KeyError,
            TypeError,
            OverflowError,
        ) as error:
            # Never include a provider response, token, SQL arguments or URL in errors.
            category, status = "protocol", 0
            if isinstance(error, (httpx.TimeoutException, TimeoutError)):
                category = "timeout"
            elif isinstance(error, httpx.HTTPStatusError):
                category, status = "http_status", error.response.status_code
            elif isinstance(error, httpx.HTTPError):
                category = "transport"
            raise JournalFailure(
                category, phase, int((time.monotonic() - started) * 1000), status
            ) from None

    async def initialize(self) -> list[dict]:
        started = time.monotonic()
        await self.execute(
            f"CREATE TABLE IF NOT EXISTS {LEASE} "
            "(id INTEGER PRIMARY KEY CHECK(id=1),owner TEXT NOT NULL,expires INTEGER NOT NULL)",
            phase="lease_schema",
        )
        rows = await self.execute(
            f"INSERT INTO {LEASE}(id,owner,expires) VALUES(1,?,unixepoch()+30) "
            "ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,expires=excluded.expires "
            f"WHERE {LEASE}.expires<unixepoch() RETURNING owner",
            (self.owner,),
            phase="lease_acquire",
        )
        if rows != [{"owner": self.owner}]:
            raise JournalAlreadyOwned("Simulation journal already has a live owner")
        await self.execute(
            f"CREATE TABLE IF NOT EXISTS {TABLE} (id TEXT PRIMARY KEY,owner TEXT NOT NULL,"
            "proposal TEXT NOT NULL,state TEXT NOT NULL,reason TEXT NOT NULL,"
            "created REAL NOT NULL,position REAL NOT NULL DEFAULT 0)",
            phase="history_schema",
        )
        rows = await self.execute(
            f"SELECT {','.join(COLUMNS)} FROM {TABLE} LIMIT 10001", phase="history_read"
        )
        if len(rows) > 10000:
            raise JournalFailure(
                "capacity", "history_validate", int((time.monotonic() - started) * 1000)
            )
        for row in rows:
            if (
                set(row) != set(COLUMNS)
                or row["state"] not in ("proposed", "running", "completed", "cancelled")
                or not all(isinstance(row[col], str) for col in COLUMNS[:5])
                or len(row["proposal"]) > 16384
                or not all(isinstance(row[col], (int, float)) for col in COLUMNS[5:])
            ):
                raise JournalFailure(
                    "schema", "history_validate", int((time.monotonic() - started) * 1000)
                )
        return rows

    async def save(self, row: dict) -> None:
        started = time.monotonic()
        expected = {col: row[col] for col in COLUMNS}
        try:
            saved = await self.execute(
                f"INSERT INTO {TABLE}({','.join(COLUMNS)}) SELECT ?,?,?,?,?,?,? "
                f"WHERE EXISTS(SELECT 1 FROM {LEASE} "
                "WHERE id=1 AND owner=? AND expires>unixepoch()) "
                "ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,proposal=excluded.proposal,"
                "state=excluded.state,reason=excluded.reason,created=excluded.created,"
                "position=excluded.position RETURNING id",
                (*expected.values(), self.owner),
                phase="task_save",
            )
        except JournalFailure as error:
            if error.category not in {"timeout", "transport"}:
                raise
            # The write may have committed before its acknowledgement was lost.
            # Observe once, under the same live lease; never retry the write.
            try:
                persisted = await self.execute(
                    f"SELECT {','.join(COLUMNS)} FROM {TABLE} WHERE id=? "
                    f"AND EXISTS(SELECT 1 FROM {LEASE} "
                    "WHERE id=1 AND owner=? AND expires>unixepoch())",
                    (expected["id"], self.owner),
                    phase="task_save_reconcile",
                )
            except JournalFailure:
                raise error from None
            if persisted == [expected]:
                return
            raise error from None
        if saved != [{"id": row["id"]}]:
            raise JournalFailure("ownership", "task_save", int((time.monotonic() - started) * 1000))

    async def renew(self) -> None:
        started = time.monotonic()
        rows = await self.execute(
            f"UPDATE {LEASE} SET expires=unixepoch()+30 "
            "WHERE id=1 AND owner=? AND expires>unixepoch() RETURNING owner",
            (self.owner,),
            phase="lease_renew",
        )
        if rows != [{"owner": self.owner}]:
            raise JournalFailure(
                "ownership", "lease_renew", int((time.monotonic() - started) * 1000)
            )

    async def probe(self) -> None:
        started = time.monotonic()
        rows = await self.execute(
            f"SELECT owner FROM {LEASE} WHERE id=1 AND owner=? AND expires>unixepoch()",
            (self.owner,),
            phase="lease_probe",
        )
        if rows != [{"owner": self.owner}]:
            raise JournalFailure(
                "ownership", "lease_probe", int((time.monotonic() - started) * 1000)
            )

    async def close(self) -> None:
        # All local writers have been joined before shutdown. Owner scoping and
        # guarded writes prevent an obsolete process from touching a new owner.
        try:
            await self.execute(
                f"DELETE FROM {LEASE} WHERE id=1 AND owner=?", (self.owner,), phase="lease_release"
            )
        except sqlite3.Error:
            pass  # An unreachable/expired owner is fenced by the 30-second lease.
        finally:
            await self.client.aclose()
