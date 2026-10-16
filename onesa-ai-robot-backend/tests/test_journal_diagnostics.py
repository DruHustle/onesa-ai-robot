"""Fixed journal diagnostics at synthetic HTTP and simulator safety boundaries."""

import asyncio
import json
import logging
import sqlite3
import time
from contextlib import asynccontextmanager

import httpx
import pytest
from pydantic import SecretStr

from robot_api.main import State
from robot_api.turso import MAX_RESPONSE_BYTES, JournalFailure, TursoJournal
from tests.test_simulation import approve, login, proposal, reset
from tests.test_turso import URL, client, config
from tests.test_turso import remote as remote

SENTINEL = "synthetic-private-token-SQL-row-https://secret.example"


def payload(cells=None):
    return {
        "results": [
            {
                "type": "ok",
                "response": {
                    "type": "execute",
                    "result": {"cols": [{"name": "owner"}], "rows": cells or []},
                },
            },
            {"type": "ok", "response": {"type": "close"}},
        ]
    }


@asynccontextmanager
async def mocked(handler):
    journal = TursoJournal(URL, SecretStr(SENTINEL))
    timeout = journal.client.timeout
    await journal.client.aclose()
    journal.client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), timeout=timeout, trust_env=False
    )
    try:
        yield journal
    finally:
        await journal.client.aclose()


@pytest.mark.parametrize(
    "kind,category",
    [
        (httpx.ConnectTimeout, "timeout"),
        (httpx.ReadTimeout, "timeout"),
        (httpx.WriteTimeout, "timeout"),
        (httpx.PoolTimeout, "timeout"),
        (httpx.ConnectError, "transport"),
        (httpx.ReadError, "transport"),
        (httpx.WriteError, "transport"),
        (httpx.RemoteProtocolError, "transport"),
    ],
)
def test_fixed_transport_categories_no_retry_or_exception_contents(kind, category):
    async def scenario():
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            raise kind(SENTINEL, request=request)

        async with mocked(handler) as journal:
            with pytest.raises(JournalFailure) as caught:
                await journal.execute(SENTINEL, (SENTINEL,), phase="task_save")
        failure = caught.value
        assert (failure.category, failure.phase, failure.http_status) == (category, "task_save", 0)
        assert 0 <= failure.elapsed_ms <= 120_000
        assert failure.__suppress_context__ and failure.__cause__ is None
        assert SENTINEL not in str(failure) + repr(vars(failure)) + repr(failure.args)
        assert calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("status", [307, 403, 429, 500, 503])
def test_http_status_is_numeric_and_response_is_not_logged(status):
    async def scenario():
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(status, content=SENTINEL, headers={"Location": SENTINEL})

        async with mocked(handler) as journal:
            with pytest.raises(JournalFailure) as caught:
                await journal.execute(SENTINEL, phase="lease_renew")
        assert (caught.value.category, caught.value.phase, caught.value.http_status) == (
            "http_status",
            "lease_renew",
            status,
        )
        assert SENTINEL not in repr(vars(caught.value)) + str(caught.value)
        assert calls == 1  # No retry or redirect, including ambiguous writes.

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["json", "shape", "cell", "number", "width", "oversize"])
def test_invalid_protocol_is_redacted_and_bounded(kind):
    async def scenario():
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            if kind == "json":
                return httpx.Response(200, content=SENTINEL)
            if kind == "oversize":
                return httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))
            body = payload()
            if kind == "shape":
                body = {"results": [{"type": SENTINEL}]}
            if kind == "cell":
                body = payload([[{"type": "blob", "value": SENTINEL}]])
            if kind == "number":
                body = payload([[{"type": "float", "value": "NaN"}]])
            if kind == "width":
                body = payload([[{"type": "text", "value": SENTINEL}] * 2])
            return httpx.Response(200, json=body)

        async with mocked(handler) as journal:
            with pytest.raises(JournalFailure) as caught:
                await journal.execute(SENTINEL, phase="history_read")
        assert (caught.value.category, caught.value.phase) == ("protocol", "history_read")
        assert SENTINEL not in str(caught.value) + repr(vars(caught.value))
        assert calls == 1

    asyncio.run(scenario())


def test_real_configured_http_client_retains_two_second_statement_deadline():
    async def scenario():
        calls = 0
        handlers = set()

        async def handle(reader, writer):
            nonlocal calls
            task = asyncio.current_task()
            handlers.add(task)
            try:
                headers = await reader.readuntil(b"\r\n\r\n")
                length = next(
                    int(line.split(b":", 1)[1])
                    for line in headers.split(b"\r\n")
                    if line.lower().startswith(b"content-length:")
                )
                await reader.readexactly(length)
                calls += 1
                await asyncio.sleep(5)  # Headers never arrive within the real read budget.
            finally:
                writer.close()
                await writer.wait_closed()
                handlers.discard(task)

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        journal = TursoJournal(URL, SecretStr(SENTINEL))
        try:
            assert all(
                getattr(journal.client.timeout, part) == limit
                for part, limit in (("connect", 1.0), ("read", 2.0), ("write", 1.0), ("pool", 1.0))
            )
            journal.url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/fixture"
            started = time.monotonic()
            with pytest.raises(JournalFailure) as caught:
                await journal.execute(SENTINEL, phase="task_save")
            elapsed = time.monotonic() - started
            assert caught.value.category == "timeout" and caught.value.phase == "task_save"
            assert 1.8 <= elapsed < 2.3
            assert 1800 <= caught.value.elapsed_ms < 2300
            assert calls == 1
        finally:
            await journal.client.aclose()
            server.close()
            await server.wait_closed()
            pending = list(handlers)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    asyncio.run(scenario())


def test_outer_two_second_bound_cancels_a_stalled_response_once():
    async def scenario():
        calls = 0
        cancelled = False

        class Stalled(httpx.AsyncByteStream):
            async def __aiter__(self):
                nonlocal cancelled
                try:
                    await asyncio.sleep(5)
                    yield b"unused"
                except asyncio.CancelledError:
                    cancelled = True
                    raise

        async def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(200, stream=Stalled())

        async with mocked(handler) as journal:
            started = time.monotonic()
            with pytest.raises(JournalFailure) as caught:
                await journal.execute(SENTINEL, phase="lease_probe")
        assert caught.value.category == "timeout" and caught.value.phase == "lease_probe"
        assert 1.85 <= time.monotonic() - started < 2.8
        assert 1850 <= caught.value.elapsed_ms < 2800
        assert calls == 1 and cancelled

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "operation,phase", [("save", "task_save"), ("renew", "lease_renew"), ("probe", "lease_probe")]
)
def test_owner_rejection_stays_fenced_and_identifies_explicit_operation(operation, phase):
    async def scenario():
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=payload())

        row = dict(
            id=SENTINEL,
            owner=SENTINEL,
            proposal="{}",
            state="running",
            reason="",
            created=1.0,
            position=0.0,
        )
        async with mocked(handler) as journal:
            with pytest.raises(JournalFailure, match="ownership expired") as caught:
                await (journal.save(row) if operation == "save" else getattr(journal, operation)())
        assert (caught.value.category, caught.value.phase) == ("ownership", phase)
        assert SENTINEL not in repr(vars(caught.value)) + str(caught.value)
        assert calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["schema", "capacity"])
def test_history_validation_category_and_phase_without_extra_queries(kind):
    async def scenario():
        calls = []

        async def handler(request):
            stmt = json.loads(request.content)["requests"][0]["stmt"]
            calls.append(stmt["sql"])
            if len(calls) == 2:
                return httpx.Response(
                    200, json=payload([[{"type": "text", "value": journal.owner}]])
                )
            if len(calls) == 4:
                rows = [[{"type": "text", "value": SENTINEL}]] * (
                    10001 if kind == "capacity" else 1
                )
                return httpx.Response(200, json=payload(rows))
            return httpx.Response(200, json=payload())

        async with mocked(handler) as journal:
            with pytest.raises(JournalFailure) as caught:
                await journal.initialize()
        assert (caught.value.category, caught.value.phase) == (kind, "history_validate")
        assert SENTINEL not in repr(vars(caught.value)) + str(caught.value)
        assert len(calls) == 4  # Existing schema/acquire/schema/history sequence only.

    asyncio.run(scenario())


def test_lifecycle_cancellation_is_not_reclassified_or_retried(caplog, tmp_path):
    async def scenario():
        calls = 0
        started = asyncio.Event()

        async def handler(request):
            nonlocal calls
            calls += 1
            started.set()
            await asyncio.Event().wait()

        async with mocked(handler) as journal:
            task = asyncio.create_task(journal.execute(SENTINEL, phase="task_save"))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert calls == 1
        sim = State(config(tmp_path))
        await sim.journal.client.aclose()

        class CancelledJournal:
            async def save(self, row):
                raise asyncio.CancelledError

            async def renew(self):
                raise asyncio.CancelledError

        sim.journal = CancelledJournal()
        sim.db.execute(
            "INSERT INTO tasks VALUES(?,?,?,?,?,?,?)",
            ("owned", "owned", "{}", "running", "", 1.0, 0.0),
        )
        sim.db.commit()
        sim.dirty("owned")
        try:
            with pytest.raises(asyncio.CancelledError):
                await sim.flush_journal()
            with pytest.raises(asyncio.CancelledError):
                await sim.refresh_journal_lease()
            assert not sim.journal_failed
            assert sim.db.execute("SELECT state FROM tasks").fetchone()[0] == "running"
            assert sim.journal_dirty == {"owned": 1}
        finally:
            sim.db.close()

    with caplog.at_level(logging.WARNING, logger="robot_api.journal"):
        asyncio.run(scenario())
    assert not [record for record in caplog.records if record.name == "robot_api.journal"]


def test_first_latch_only_redacted_warning_stops_authority_and_keeps_public_503(
    remote, tmp_path, caplog
):
    _, network = remote
    with (
        client(config(tmp_path)) as api,
        caplog.at_level(logging.WARNING, logger="robot_api.journal"),
    ):
        login(api)
        reset(api)
        identifier = approve(api, proposal(duration_seconds=5))
        sim = api.app.state.sim
        assert api.portal.call(lambda: sim.active is not None)
        calls = network["calls"]
        epoch = sim.stop_epoch
        api.portal.call(lambda: sim.fail_journal(JournalFailure("timeout", "task_save", 123, 0)))
        api.portal.call(
            lambda: sim.fail_journal(sqlite3.OperationalError(SENTINEL), phase=SENTINEL)
        )
        with pytest.raises(sqlite3.OperationalError, match="requires recovery"):
            api.portal.call(sim.flush_journal)
        for _ in range(3):
            response = api.get("/api/v1/ready")
            assert response.status_code == 503
            assert response.json() == {"detail": "Remote simulation journal requires recovery"}
        assert api.portal.call(lambda: sim.stopped and sim.active is None)
        assert sim.stop_epoch > epoch
        assert (
            api.portal.call(
                lambda: sim.db.execute(
                    "SELECT state FROM tasks WHERE id=?", (identifier,)
                ).fetchone()[0]
            )
            == "cancelled"
        )
        assert network["calls"] == calls  # Failure/readiness does not retry remote writes.
        records = [record for record in caplog.records if record.name == "robot_api.journal"]
        assert len(records) == 1
        record = records[0]
        assert record.args == ("timeout", "task_save", 123, 0, "none", "not_attempted")
        assert record.exc_info is None and record.stack_info is None
        assert SENTINEL not in repr(vars(record)) + record.getMessage()


def test_untrusted_metadata_is_allowlisted_and_numeric_fields_are_clamped(remote, tmp_path, caplog):
    failure = JournalFailure(SENTINEL, SENTINEL, 999_999_999, 999)
    assert (failure.category, failure.phase, failure.elapsed_ms, failure.http_status) == (
        "unknown",
        "unknown",
        120_000,
        0,
    )
    assert JournalFailure("timeout", "query", -1, True).elapsed_ms == 0
    assert JournalFailure("timeout", "query", SENTINEL, SENTINEL).elapsed_ms == 0
    with (
        client(config(tmp_path)) as api,
        caplog.at_level(logging.WARNING, logger="robot_api.journal"),
    ):
        # Even mutated exception metadata is revalidated before it reaches the logger.
        failure.category, failure.phase, failure.elapsed_ms = SENTINEL, SENTINEL, SENTINEL
        failure.transport_kind, failure.reconciliation = SENTINEL, SENTINEL
        api.portal.call(lambda: api.app.state.sim.fail_journal(failure))
        records = [record for record in caplog.records if record.name == "robot_api.journal"]
        assert len(records) == 1 and records[0].args == (
            "unknown",
            "unknown",
            0,
            0,
            "other",
            "not_confirmed",
        )
        assert SENTINEL not in repr(vars(records[0]))


def test_generic_sqlite_failure_logs_no_exception_text_or_arguments(remote, tmp_path, caplog):
    with (
        client(config(tmp_path)) as api,
        caplog.at_level(logging.WARNING, logger="robot_api.journal"),
    ):
        error = sqlite3.OperationalError(SENTINEL, {"sql": SENTINEL, "row": SENTINEL})
        api.portal.call(lambda: api.app.state.sim.fail_journal(error, phase="flush"))
        records = [record for record in caplog.records if record.name == "robot_api.journal"]
        assert len(records) == 1
        assert records[0].args == ("sqlite", "flush", 0, 0, "none", "not_attempted")
        assert records[0].exc_info is None and records[0].stack_info is None
        assert SENTINEL not in repr(vars(records[0]))
        assert api.get("/api/v1/ready").json() == {
            "detail": "Remote simulation journal requires recovery"
        }


def test_stale_readiness_latches_once_without_an_extra_remote_probe(remote, tmp_path, caplog):
    _, network = remote
    with (
        client(config(tmp_path)) as api,
        caplog.at_level(logging.WARNING, logger="robot_api.journal"),
    ):
        sim = api.app.state.sim
        api.portal.call(lambda: setattr(sim, "journal_lease_confirmed_at", time.monotonic() - 16))
        calls = network["calls"]
        response = api.get("/api/v1/ready")
        assert (
            response.status_code == 503
            and response.json()["detail"] == "Remote simulation journal lease check expired"
        )
        assert api.get("/api/v1/ready").status_code == 503
        assert network["calls"] == calls
        records = [record for record in caplog.records if record.name == "robot_api.journal"]
        assert len(records) == 1
        assert records[0].args[0:2] == ("lease_stale", "ready")
        assert 15_000 < records[0].args[2] <= 120_000


@pytest.mark.parametrize("operation,phase", [("flush", "task_save"), ("renew", "lease_renew")])
def test_actual_http_failure_latches_at_its_operation_without_replay(
    remote, tmp_path, caplog, operation, phase
):
    _, network = remote
    with (
        client(config(tmp_path)) as api,
        caplog.at_level(logging.WARNING, logger="robot_api.journal"),
    ):
        login(api)
        reset(api)
        identifier = approve(api, proposal(duration_seconds=5))
        sim = api.app.state.sim
        action = sim.flush_journal if operation == "flush" else sim.refresh_journal_lease

        async def inject_and_observe():
            # Fault injection and the targeted operation share the simulator's
            # loop. A background tick must not consume the fault in the gap
            # between a test-thread assignment and portal.call().
            if operation == "flush":
                sim.dirty(identifier)
            calls = network["calls"]
            network["offline"] = True
            with pytest.raises(JournalFailure):
                await action()
            return calls

        calls = api.portal.call(inject_and_observe)
        assert network["calls"] == calls + 1
        assert api.portal.call(lambda: sim.journal_failed and sim.stopped and sim.active is None)
        assert api.get("/api/v1/ready").json() == {
            "detail": "Remote simulation journal requires recovery"
        }
        with pytest.raises(sqlite3.OperationalError, match="requires recovery"):
            api.portal.call(action)
        assert network["calls"] == calls + 1
        records = [record for record in caplog.records if record.name == "robot_api.journal"]
        assert len(records) == 1
        assert records[0].args[0:2] == ("http_status", phase)
        assert records[0].args[3] == 403
        assert records[0].exc_info is None and records[0].stack_info is None


def test_standby_deadline_records_one_fixed_warning_without_stealing_owner(
    remote, tmp_path, monkeypatch, caplog
):
    import robot_api.main as main

    monkeypatch.setattr(main, "JOURNAL_STARTUP_SECONDS", 0)
    with client(config(tmp_path)) as prior:
        with (
            client(config(tmp_path)) as standby,
            caplog.at_level(logging.WARNING, logger="robot_api.journal"),
        ):
            deadline = time.monotonic() + 2
            while standby.get("/api/v1/health").status_code != 503:
                assert time.monotonic() < deadline
                time.sleep(0.01)
            assert standby.get("/api/v1/ready").status_code == 503
            assert prior.get("/api/v1/ready").status_code == 200
            records = [record for record in caplog.records if record.name == "robot_api.journal"]
            assert len(records) == 1
            assert records[0].args[0:2] == ("startup_deadline", "initialize")
