"""Real SQLite statements prove dropped-connection recovery cannot clobber later history."""

import asyncio
import sqlite3

import httpx
import pytest
from pydantic import SecretStr

from robot_api.turso import COLUMNS, TABLE, JournalFailure, TursoJournal
from tests.test_turso import TOKEN, URL
from tests.test_turso import remote as remote


def row(state="proposed"):
    return dict(
        zip(
            COLUMNS,
            ("conditional-owned", "operator", "{}", state, "fixture", 1.25, 0.0),
            strict=True,
        )
    )


@pytest.mark.parametrize("existing", [False, True])
def test_dropped_uncommitted_save_retries_same_record_once(remote, existing):
    path, network = remote
    calls = []

    def drop_first(sql):
        if sql.startswith(f"INSERT INTO {TABLE}"):
            calls.append(sql)
            if len(calls) == 1:
                raise httpx.RemoteProtocolError("synthetic private connection closed")

    async def run():
        journal = TursoJournal(URL, SecretStr(TOKEN))
        try:
            await journal.initialize()
            if existing:
                await journal.save(row())
            desired = row("running") if existing else row()
            network["before_execute"] = drop_first
            await journal.save(desired)
            assert len(calls) == 2 and calls[0] == calls[1]
            with sqlite3.connect(path) as db:
                assert db.execute(f"SELECT {','.join(COLUMNS)} FROM {TABLE}").fetchall() == [
                    tuple(desired.values())
                ]
        finally:
            network["before_execute"] = None
            await journal.close()

    asyncio.run(run())


def test_committed_dropped_ack_is_observed_without_another_write(remote):
    _, network = remote
    calls = []

    def drop_ack(sql):
        if sql.startswith(f"INSERT INTO {TABLE}"):
            calls.append(sql)
            raise httpx.RemoteProtocolError("synthetic private ack lost")

    async def run():
        journal = TursoJournal(URL, SecretStr(TOKEN))
        try:
            await journal.initialize()
            network["after_execute"] = drop_ack
            await journal.save(row())
            assert len(calls) == 1
        finally:
            network["after_execute"] = None
            await journal.close()

    asyncio.run(run())


def test_late_old_conditional_write_cannot_replace_newer_acknowledged_state(remote):
    path, _ = remote

    async def run():
        journal = TursoJournal(URL, SecretStr(TOKEN))
        original = journal.execute
        captured = []
        try:
            await journal.initialize()
            await journal.save(row())

            async def capture(sql, args=(), *, phase="query"):
                if phase == "task_save":
                    captured.append((sql, args))
                return await original(sql, args, phase=phase)

            journal.execute = capture
            await journal.save(row("running"))
            old_sql, old_args = captured[0]
            await journal.save(row("completed"))
            with sqlite3.connect(path) as db:
                # This models the original request arriving after its retry and
                # a newer revision. SQLite evaluates the guard atomically now.
                assert db.execute(old_sql, old_args).fetchall() == []
                assert db.execute(f"SELECT state FROM {TABLE}").fetchone() == ("completed",)
        finally:
            await journal.close()

    asyncio.run(run())


@pytest.mark.parametrize("change", ["missing", "newer"])
def test_changed_or_missing_known_history_is_never_recreated(remote, change):
    path, network = remote
    writes = []

    def drop(sql):
        if sql.startswith(f"INSERT INTO {TABLE}"):
            writes.append(sql)
            raise httpx.RemoteProtocolError("synthetic private drop")

    async def run():
        journal = TursoJournal(URL, SecretStr(TOKEN))
        try:
            await journal.initialize()
            await journal.save(row())
            with sqlite3.connect(path) as db:
                if change == "missing":
                    db.execute(f"DELETE FROM {TABLE}")
                else:
                    db.execute(f"UPDATE {TABLE} SET state='completed'")
            network["before_execute"] = drop
            with pytest.raises(JournalFailure):
                await journal.save(row("running"))
            assert len(writes) == 1
            with sqlite3.connect(path) as db:
                assert db.execute(f"SELECT state FROM {TABLE}").fetchall() == (
                    [] if change == "missing" else [("completed",)]
                )
        finally:
            network["before_execute"] = None
            await journal.close()

    asyncio.run(run())


def test_a_second_dropped_send_stops_without_an_unbounded_loop(remote):
    _, network = remote
    writes = []

    def drop(sql):
        if sql.startswith(f"INSERT INTO {TABLE}"):
            writes.append(sql)
            raise httpx.RemoteProtocolError("synthetic private drop")

    async def run():
        journal = TursoJournal(URL, SecretStr(TOKEN))
        try:
            await journal.initialize()
            network["before_execute"] = drop
            with pytest.raises(JournalFailure) as caught:
                await journal.save(row())
            assert caught.value.reconciliation == "not_confirmed"
            assert len(writes) == 2
        finally:
            network["before_execute"] = None
            await journal.close()

    asyncio.run(run())


def test_restored_history_supplies_the_exact_previous_state_guard(remote):
    path, _ = remote

    async def run():
        first = TursoJournal(URL, SecretStr(TOKEN))
        await first.initialize()
        await first.save(row())
        await first.close()
        second = TursoJournal(URL, SecretStr(TOKEN))
        try:
            restored = await second.initialize()
            assert restored == [row()]
            await second.save(row("cancelled"))
            with sqlite3.connect(path) as db:
                assert db.execute(f"SELECT state FROM {TABLE}").fetchone() == ("cancelled",)
        finally:
            await second.close()

    asyncio.run(run())
