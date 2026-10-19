"""Offline proposal: a longer read cannot extend stale or foreign authority."""

import asyncio
import json
import time

import pytest
from pydantic import SecretStr

from robot_api.main import JOURNAL_RENEW_SECONDS
from robot_api.turso import (
    LEASE,
    LEASE_CONFIRM_FRESH_SECONDS,
    LEASE_READINESS_SECONDS,
    RENEW_CONFIRM_SECONDS,
    RENEW_TOTAL_SECONDS,
    STATEMENT_SECONDS,
    JournalFailure,
    TursoJournal,
)
from tests.test_turso import TOKEN, URL
from tests.test_turso import remote as remote


def test_freshness_and_renewal_fit_the_existing_readiness_window():
    assert STATEMENT_SECONDS == 2
    assert RENEW_CONFIRM_SECONDS == 5
    assert LEASE_READINESS_SECONDS == 15
    assert LEASE_CONFIRM_FRESH_SECONDS == 18
    assert LEASE_READINESS_SECONDS + RENEW_CONFIRM_SECONDS + 1 == 21
    assert JOURNAL_RENEW_SECONDS + RENEW_TOTAL_SECONDS < LEASE_READINESS_SECONDS


@pytest.mark.parametrize("write_delay", [0, 2.01])
def test_three_second_confirmation_is_readonly_and_never_replays_update(remote, write_delay):
    _, network = remote

    async def run():
        journal = TursoJournal(URL, SecretStr(TOKEN))
        try:
            await journal.initialize()
            execute = journal.execute
            phases = []

            async def uncertain(sql, args=(), *, phase="query"):
                phases.append(phase)
                if phase == "lease_renew":
                    await execute(sql, args, phase=phase)
                    await asyncio.sleep(write_delay)
                    raise JournalFailure("timeout", phase, 2010, transport_kind="ReadTimeout")
                network["delay"] = 3.05
                return await execute(sql, args, phase=phase)

            journal.execute = uncertain
            started = time.monotonic()
            await journal.renew()
            elapsed = time.monotonic() - started
            assert 3 <= elapsed < 6
            assert phases == ["lease_renew", "lease_renew_reconcile"]
        finally:
            network["delay"] = 0
            await journal.close()

    asyncio.run(run())


@pytest.mark.parametrize("sql", ["UPDATE fake SET value=1", "SELECT 1"])
def test_extended_phase_rejects_other_statements_before_network(remote, sql):
    _, network = remote

    async def run():
        journal = TursoJournal(URL, SecretStr(TOKEN))
        calls = network["calls"]
        try:
            with pytest.raises(JournalFailure) as caught:
                await journal.execute(sql, (journal.owner,), phase="lease_renew_reconcile")
            assert caught.value.category == "protocol"
            assert network["calls"] == calls
        finally:
            await journal.client.aclose()

    asyncio.run(run())


def test_actual_http_read_confirmation_can_complete_after_two_seconds(monkeypatch):
    import robot_api.turso as module

    async def run():
        handlers, requests = set(), []
        journal = None

        async def respond(reader, writer):
            task = asyncio.current_task()
            handlers.add(task)
            try:
                head = await reader.readuntil(b"\r\n\r\n")
                length = next(
                    int(line.split(b":", 1)[1])
                    for line in head.split(b"\r\n")
                    if line.lower().startswith(b"content-length:")
                )
                body = json.loads(await reader.readexactly(length))
                stmt = body["requests"][0]["stmt"]
                requests.append(stmt["sql"])
                assert stmt["sql"].startswith(
                    "SELECT owner,expires-unixepoch() AS remaining FROM " + LEASE
                )
                await asyncio.sleep(3.05)
                data = json.dumps(
                    {
                        "results": [
                            {
                                "type": "ok",
                                "response": {
                                    "type": "execute",
                                    "result": {
                                        "cols": [{"name": "owner"}, {"name": "remaining"}],
                                        "rows": [
                                            [
                                                {"type": "text", "value": journal.owner},
                                                {"type": "integer", "value": "30"},
                                            ]
                                        ],
                                    },
                                },
                            },
                            {"type": "ok", "response": {"type": "close"}},
                        ]
                    }
                ).encode()
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Length: "
                    + str(len(data)).encode()
                    + b"\r\nConnection: close\r\n\r\n"
                    + data
                )
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
                handlers.discard(task)

        server = await asyncio.start_server(respond, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        monkeypatch.setattr(module, "endpoint", lambda _: f"http://127.0.0.1:{port}/v2/pipeline")
        journal = TursoJournal(URL, SecretStr(TOKEN))
        try:
            rows = await journal.execute(
                f"SELECT owner,expires-unixepoch() AS remaining FROM {LEASE} "
                "WHERE id=1 AND owner=? AND expires>=unixepoch()+18",
                (journal.owner,),
                phase="lease_renew_reconcile",
            )
            assert rows == [{"owner": journal.owner, "remaining": 30}]
            assert len(requests) == 1
        finally:
            await journal.client.aclose()
            server.close()
            await server.wait_closed()
            for task in list(handlers):
                task.cancel()
            await asyncio.gather(*handlers, return_exceptions=True)

    asyncio.run(run())


@pytest.mark.parametrize(
    "remaining,elapsed,accepted",
    [
        (18, 0, True),
        (18, 2, True),
        (18, 2.1, False),
        (18, 3, False),
        (20, 3, True),
        (21, 5, True),
        (21, 5.01, False),
        (17, 0, False),
        (31, 0, False),
        (True, 0, False),
        (24.0, 0, False),
        ("24", 0, False),
    ],
)
def test_actual_response_age_must_leave_full_readiness_authority(
    monkeypatch, remaining, elapsed, accepted
):
    from types import SimpleNamespace

    import robot_api.turso as module

    async def run():
        clock = SimpleNamespace(now=0.0)
        monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock.now))
        journal = TursoJournal(URL, SecretStr(TOKEN))
        phases = []

        async def execute(sql, args=(), *, phase="query"):
            phases.append(phase)
            if phase == "lease_renew":
                clock.now += 2
                raise JournalFailure("timeout", phase, 2000)
            assert phase == "lease_renew_reconcile" and sql.startswith("SELECT ")
            clock.now += elapsed
            return [{"owner": journal.owner, "remaining": remaining}]

        journal.execute = execute
        try:
            if accepted:
                await journal.renew()
            else:
                with pytest.raises(JournalFailure) as caught:
                    await journal.renew()
                assert caught.value.reconciliation == "not_confirmed"
            assert phases == ["lease_renew", "lease_renew_reconcile"]
        finally:
            await journal.client.aclose()

    asyncio.run(run())
