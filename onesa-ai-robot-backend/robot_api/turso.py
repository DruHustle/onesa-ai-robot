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
# Numeric JSON parameters can lose one ULP at the remote parser. Transport
# decimal text instead, with SQLite performing the explicit REAL conversion.
# Read numeric history as high-precision text too; do not weaken exact equality.
READ_COLUMNS = ",".join(
    [*COLUMNS[:5]]
    + [
        f"CASE WHEN typeof({column})='real' THEN printf('%!.26g',{column}) "
        f"WHEN typeof({column})='integer' THEN {column} ELSE NULL END AS {column}"
        for column in COLUMNS[5:]
    ]
)
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
STATEMENT_SECONDS = 2
SAVE_TOTAL_SECONDS = 4 * STATEMENT_SECONDS
RENEW_CONFIRM_SECONDS = 5
RENEW_TOTAL_SECONDS = STATEMENT_SECONDS + RENEW_CONFIRM_SECONDS
LEASE_READINESS_SECONDS = 15
LEASE_CONFIRM_FRESH_SECONDS = 18
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
        "lease_renew_reconcile",
        "lease_probe",
        "lease_release",
        "initialize",
        "flush",
        "ready",
        "unknown",
    }
)
TRANSPORT_KINDS = frozenset(
    {
        "none",
        "ConnectError",
        "ConnectTimeout",
        "PoolTimeout",
        "ReadError",
        "ReadTimeout",
        "WriteError",
        "WriteTimeout",
        "RemoteProtocolError",
        "LocalProtocolError",
        "ProxyError",
        "UnsupportedProtocol",
        "other",
    }
)


class JournalFailure(sqlite3.OperationalError):
    """Fixed diagnostic metadata; never copy exception or provider contents."""

    def __init__(
        self,
        category: str,
        phase: str,
        elapsed_ms: int = 0,
        http_status: int = 0,
        *,
        transport_kind: str = "none",
        reconciliation: str = "not_attempted",
    ):
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
        self.transport_kind = transport_kind if transport_kind in TRANSPORT_KINDS else "other"
        self.reconciliation = (
            reconciliation
            if reconciliation in {"not_attempted", "unavailable", "not_confirmed"}
            else "not_confirmed"
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
        self.acknowledged: dict[str, dict] = {}
        self.url = endpoint(url)
        self.client = httpx.AsyncClient(
            headers={"Authorization": "Bearer " + token.get_secret_value()},
            # Ordinary statements retain their two-second bound. Only the
            # exact read-only renewal confirmation may use its separately
            # bounded five-second response budget in execute().
            timeout=httpx.Timeout(1.0, read=2.0),
            # Retry only connection establishment, before any HTTP request is sent.
            # Read/write/protocol failures never replay a statement. Reuse at most
            # two healthy connections for ten idle seconds; HTTPcore discards
            # disconnected/expired idle sockets before sending. The existing
            # two-second overall deadline remains unchanged.
            transport=httpx.AsyncHTTPTransport(
                retries=1,
                limits=httpx.Limits(
                    max_connections=2, max_keepalive_connections=2, keepalive_expiry=10.0
                ),
                trust_env=False,
            ),
            follow_redirects=False,
            trust_env=False,
        )

    async def execute(self, sql: str, args: tuple = (), *, phase: str = "query") -> list[dict]:
        # No statement retries: a timeout may follow a committed write.
        def encode(value):
            if value is None:
                return {"type": "null"}
            if isinstance(value, int):
                return {"type": "integer", "value": str(value)}
            if isinstance(value, float) and math.isfinite(value):
                return {"type": "text", "value": repr(value)}
            if isinstance(value, str):
                return {"type": "text", "value": value}
            raise ValueError("Unsupported journal parameter")

        confirmation = phase == "lease_renew_reconcile"
        confirmation_sql = (
            f"SELECT owner,expires-unixepoch() AS remaining FROM {LEASE} "
            f"WHERE id=1 AND owner=? AND expires>=unixepoch()+{LEASE_CONFIRM_FRESH_SECONDS}"
        )
        if confirmation and (sql != confirmation_sql or args != (self.owner,)):
            raise JournalFailure("protocol", phase, 0)
        # All statements are fixed internal SQL with positional placeholders;
        # user strings stay bound values, never interpolated SQL.
        wire_sql = sql
        if any(isinstance(value, float) for value in args):
            pieces = sql.split("?")
            if len(pieces) != len(args) + 1:
                raise JournalFailure("protocol", phase, 0)
            wire_sql = pieces[0] + "".join(
                ("CAST(? AS REAL)" if isinstance(value, float) else "?") + suffix
                for value, suffix in zip(args, pieces[1:], strict=True)
            )
        budget = RENEW_CONFIRM_SECONDS if confirmation else STATEMENT_SECONDS
        request_timeout = httpx.Timeout(1.0, read=budget)
        body = {
            "requests": [
                {"type": "execute", "stmt": {"sql": wire_sql, "args": [encode(v) for v in args]}},
                {"type": "close"},
            ]
        }
        started = time.monotonic()
        try:
            async with asyncio.timeout(budget):
                async with self.client.stream(
                    "POST", self.url, json=body, timeout=request_timeout
                ) as response:
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
                for column, cell in zip(columns, row, strict=True):
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
                        if (
                            phase in {"history_read", "task_save_reconcile"}
                            and column in COLUMNS[5:]
                        ):
                            number = float(value)
                            if not math.isfinite(number):
                                raise ValueError("Invalid journal number")
                            values.append(number)
                        else:
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
            RecursionError,
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
                category,
                phase,
                int((time.monotonic() - started) * 1000),
                status,
                transport_kind=type(error).__name__
                if isinstance(error, httpx.TransportError)
                else "none",
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
            f"SELECT {READ_COLUMNS} FROM {TABLE} LIMIT 10001", phase="history_read"
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
        self.acknowledged = {row["id"]: dict(row) for row in rows}
        return rows

    async def save(self, row: dict) -> None:
        started = time.monotonic()
        expected = {col: row[col] for col in COLUMNS}
        previous = self.acknowledged.get(expected["id"])
        equal = " AND ".join(f"{TABLE}.{col} IS ?" for col in COLUMNS)
        # One atomic statement accepts only the last acknowledged state or this
        # identical desired state. A late old request cannot overwrite a later
        # acknowledged revision. The independent live-owner fence still applies.
        guard = f"({equal})" if previous is not None else "0"
        sql = (
            f"INSERT INTO {TABLE}({','.join(COLUMNS)}) SELECT ?,?,?,?,?,?,? "
            f"WHERE EXISTS(SELECT 1 FROM {LEASE} "
            "WHERE id=1 AND owner=? AND expires>unixepoch()) "
            "ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,proposal=excluded.proposal,"
            "state=excluded.state,reason=excluded.reason,created=excluded.created,"
            f"position=excluded.position WHERE ({guard} OR ({equal})) RETURNING id"
        )
        args = (
            *expected.values(),
            self.owner,
            *((previous[col] for col in COLUMNS) if previous is not None else ()),
            *expected.values(),
        )

        async def persist():
            for attempt in range(2):
                try:
                    saved = await self.execute(sql, args, phase="task_save")
                except JournalFailure as error:
                    if error.category not in {"timeout", "transport"}:
                        raise
                    try:
                        persisted = await self.execute(
                            f"SELECT {READ_COLUMNS} FROM {TABLE} WHERE id=? "
                            f"AND EXISTS(SELECT 1 FROM {LEASE} "
                            "WHERE id=1 AND owner=? AND expires>unixepoch())",
                            (expected["id"], self.owner),
                            phase="task_save_reconcile",
                        )
                    except JournalFailure:
                        error.reconciliation = "unavailable"
                        raise error from None
                    if persisted == [expected]:
                        self.acknowledged[expected["id"]] = dict(expected)
                        return
                    # Only the observed dropped-connection class gets one
                    # conditional retry, after an exact prior/absent-state read.
                    # Timeouts, missing known history, changed rows, expired
                    # ownership and unavailable reads never authorize that retry.
                    prior_confirmed = persisted == ([previous] if previous is not None else [])
                    if (
                        attempt == 0
                        and error.transport_kind == "RemoteProtocolError"
                        and prior_confirmed
                    ):
                        continue
                    error.reconciliation = "not_confirmed"
                    raise error from None
                if saved != [{"id": expected["id"]}]:
                    raise JournalFailure(
                        "ownership", "task_save", int((time.monotonic() - started) * 1000)
                    )
                self.acknowledged[expected["id"]] = dict(expected)
                return

        try:
            async with asyncio.timeout(SAVE_TOTAL_SECONDS):
                await persist()
        except TimeoutError:
            raise JournalFailure(
                "timeout",
                "task_save",
                int((time.monotonic() - started) * 1000),
                reconciliation="unavailable",
            ) from None

    async def renew(self) -> None:
        started = time.monotonic()
        try:
            rows = await self.execute(
                f"UPDATE {LEASE} SET expires=unixepoch()+30 "
                "WHERE id=1 AND owner=? AND expires>unixepoch() RETURNING owner",
                (self.owner,),
                phase="lease_renew",
            )
        except JournalFailure as error:
            if error.category not in {"timeout", "transport"}:
                raise
            # Never replay an uncertain UPDATE. One same-owner SELECT may use
            # five seconds; its database lifetime must cover actual elapsed read
            # time, readiness15s and a one-second resolution margin. Retain the
            # existing18s minimum, and require up to21s for a five-second read.
            # Write2s + confirmation5s + renewal interval5s =12s, below readiness15s.
            # No other query/write receives the longer response budget.
            remaining = RENEW_TOTAL_SECONDS - (time.monotonic() - started)
            try:
                if remaining <= 0:
                    raise TimeoutError
                confirmation_started = time.monotonic()
                async with asyncio.timeout(remaining):
                    confirmed = await self.execute(
                        f"SELECT owner,expires-unixepoch() AS remaining FROM {LEASE} "
                        "WHERE id=1 AND owner=? AND "
                        f"expires>=unixepoch()+{LEASE_CONFIRM_FRESH_SECONDS}",
                        (self.owner,),
                        phase="lease_renew_reconcile",
                    )
            except (JournalFailure, TimeoutError):
                error.reconciliation = "unavailable"
                error.elapsed_ms = min(120_000, int((time.monotonic() - started) * 1000))
                raise error from None
            read_elapsed = time.monotonic() - confirmation_started
            if (
                0 <= read_elapsed <= RENEW_CONFIRM_SECONDS
                and len(confirmed) == 1
                and set(confirmed[0]) == {"owner", "remaining"}
                and confirmed[0]["owner"] == self.owner
                and type(confirmed[0]["remaining"]) is int
                and LEASE_CONFIRM_FRESH_SECONDS <= confirmed[0]["remaining"] <= 30
                and confirmed[0]["remaining"] - read_elapsed >= LEASE_READINESS_SECONDS + 1
            ):
                return
            error.reconciliation = "not_confirmed"
            error.elapsed_ms = min(120_000, int((time.monotonic() - started) * 1000))
            raise error from None
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
