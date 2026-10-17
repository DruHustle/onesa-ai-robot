"""Virtual provider/database time; no HTTP requests, credentials or real history."""

import asyncio
import importlib
import sqlite3
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from robot_api.main import State
from robot_api.turso import LEASE, JournalFailure, TursoJournal

runtime = importlib.import_module("robot_api.main")


def scenario(monkeypatch, *, delay=5.1, committed=False, foreign=False, rounds=1):
    async def run():
        clock = SimpleNamespace(now=1.2)  # Previous successful acknowledgement took 1.2s.
        database = sqlite3.connect(":memory:")
        database.row_factory = sqlite3.Row
        database.create_function("unixepoch", 0, lambda: int(clock.now))
        database.execute(f"CREATE TABLE {LEASE}(id INTEGER PRIMARY KEY,owner TEXT,expires INT)")
        journal = TursoJournal("libsql://lease-timing.example.turso.io", SecretStr("synthetic"))
        database.execute(f"INSERT INTO {LEASE} VALUES(1,?,30)", (journal.owner,))
        calls, faults = [], []

        async def execute(sql, args=(), *, phase="query"):
            calls.append((phase, sql))
            if phase == "lease_renew":
                clock.now += 2
                if committed:
                    database.execute(sql, args).fetchall()
                if foreign:
                    database.execute(f"UPDATE {LEASE} SET owner=?", ("other-synthetic-owner",))
                raise JournalFailure("timeout", phase, 2000)
            assert phase == "lease_renew_reconcile" and sql.startswith("SELECT ")
            clock.now += 2
            return [dict(row) for row in database.execute(sql, args).fetchall()]

        journal.execute = execute
        state = State.__new__(State)
        state.journal = journal
        state.journal_failed = False
        state.journal_lease_confirmed_at = clock.now

        def fault(error, **kwargs):
            state.journal_failed = True
            faults.append(error)

        state.fail_journal = fault
        monkeypatch.setattr(runtime, "time", SimpleNamespace(monotonic=lambda: clock.now))
        renewed = clock.now
        try:
            clock.now = renewed + 4.9
            assert await state.refresh_journal_when_due(renewed) == renewed
            assert calls == []
            for _ in range(rounds):
                clock.now = renewed + delay
                renewed = await state.refresh_journal_when_due(renewed)
                assert state.journal_lease_confirmed_at == renewed == clock.now
            return calls, faults, database.execute(f"SELECT expires FROM {LEASE}").fetchone()[0]
        finally:
            await journal.client.aclose()
            database.close()

    return asyncio.run(run())


@pytest.mark.parametrize("committed", [False, True])
def test_early_renewal_confirms_lease_after_uncertain_write_without_replay(monkeypatch, committed):
    calls, faults, expiry = scenario(monkeypatch, committed=committed)
    assert [phase for phase, _ in calls] == ["lease_renew", "lease_renew_reconcile"]
    assert faults == []
    if not committed:
        assert expiry == 30  # Confirmation did not extend the database lease.


def test_one_second_scheduler_jitter_retains_the_same_freshness_proof(monkeypatch):
    calls, faults, expiry = scenario(monkeypatch, delay=6.1)
    assert len(calls) == 2 and faults == [] and expiry == 30


@pytest.mark.parametrize("options", [{"delay": 10.1}, {"foreign": True}, {"rounds": 2}])
def test_late_foreign_or_repeatedly_unconfirmed_lease_still_fails_closed(monkeypatch, options):
    with pytest.raises(JournalFailure) as caught:
        scenario(monkeypatch, **options)
    assert caught.value.category == "timeout"
    assert caught.value.reconciliation == "not_confirmed"
