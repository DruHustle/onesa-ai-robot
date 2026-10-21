"""Exact history equality survives an observed one-ULP JSON transport conversion."""

import asyncio
import math
import sqlite3

import pytest
from pydantic import SecretStr

from robot_api.main import State
from robot_api.turso import COLUMNS, LEASE, TABLE, JournalFailure, TursoJournal
from tests.test_turso import TOKEN, URL, config
from tests.test_turso import remote as remote


def test_adjacent_numeric_values_round_trip_without_changing_stored_rows(remote):
    path, fault = remote
    fault["round_float_json"] = True
    values = [
        math.nextafter(value, direction)
        for value in [0.0, 0.08, 0.1, 0.15, 0.2, -0.1, 1792528893.1234567]
        for direction in [-math.inf, math.inf]
    ]

    async def run():
        journal = TursoJournal(URL, SecretStr(TOKEN))
        try:
            await journal.initialize()
            for index, value in enumerate(values):
                row = dict(
                    zip(
                        COLUMNS,
                        (str(index), "operator", "{}", "completed", "", value, value),
                        strict=True,
                    )
                )
                await journal.save(row)
            with sqlite3.connect(path) as db:
                original = db.execute(
                    f"SELECT {','.join(COLUMNS)} FROM {TABLE} ORDER BY id"
                ).fetchall()
                assert len(original) == len(values)
                for row in original:
                    assert row[5].hex() == row[6].hex() == values[int(row[0])].hex()
                db.execute(f"UPDATE {LEASE} SET expires=unixepoch()-1")
            reader = TursoJournal(URL, SecretStr(TOKEN))
            try:
                rows = await reader.initialize()
                for row in rows:
                    assert row["created"].hex() == values[int(row["id"])].hex()
                    assert row["position"].hex() == values[int(row["id"])].hex()
                with sqlite3.connect(path) as db:
                    assert (
                        db.execute(
                            f"SELECT {','.join(COLUMNS)} FROM {TABLE} ORDER BY id"
                        ).fetchall()
                        == original
                    )
            finally:
                await reader.close()
        finally:
            await journal.close()

    asyncio.run(run())


def test_numeric_projection_retains_exact_integer_types(remote):
    path, _ = remote

    async def run():
        first = TursoJournal(URL, SecretStr(TOKEN))
        second = TursoJournal(URL, SecretStr(TOKEN))
        value = (1 << 60) + 1
        try:
            await first.initialize()
            with sqlite3.connect(path) as db:
                db.execute(f"DROP TABLE {TABLE}")
                db.execute(f"CREATE TABLE {TABLE} ({','.join(COLUMNS)})")
                db.execute(
                    f"INSERT INTO {TABLE} VALUES(?,?,?,?,?,?,?)",
                    ("integer-history", "operator", "{}", "completed", "", value, value),
                )
                db.execute(f"UPDATE {LEASE} SET expires=unixepoch()-1")
            rows = await second.initialize()
            assert len(rows) == 1
            assert type(rows[0]["created"]) is int and type(rows[0]["position"]) is int
            assert rows[0]["created"] == rows[0]["position"] == value
        finally:
            await second.close()
            await first.close()

    asyncio.run(run())


def test_numeric_transport_preserves_exact_history_and_idle_recovery(remote, tmp_path):
    path, fault = remote
    fault["round_float_json"] = True

    async def run():
        sim = State(config(tmp_path))
        prior = None
        try:
            await sim.initialize_journal()
            # Establish that this boundary really reproduces the observed defect.
            value = math.nextafter(0.1, 0)
            control = await sim.journal.client.post(
                sim.journal.url,
                json={
                    "requests": [
                        {
                            "type": "execute",
                            "stmt": {
                                "sql": "SELECT ? AS value",
                                "args": [{"type": "float", "value": value}],
                            },
                        },
                        {"type": "close"},
                    ]
                },
            )
            cell = control.json()["results"][0]["response"]["result"]["rows"][0][0]
            assert cell["value"] == 0.1 and cell["value"] != value
            values = ("numeric-history", "operator", "{}", "completed", "", value, value)
            sim.db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?)", values)
            sim.db.commit()
            sim.dirty(values[0])
            await sim.flush_journal()
            with sqlite3.connect(path) as db:
                original = db.execute(f"SELECT {','.join(COLUMNS)} FROM {TABLE}").fetchall()
                assert original == [values]
                db.execute(f"UPDATE {LEASE} SET expires=unixepoch()-1")
            prior = sim.journal
            sim.fail_journal(JournalFailure("timeout", "lease_renew", 7000))
            sim.journal_recovery_next_at = 0
            assert await sim.recover_idle_journal()
            assert not sim.journal_failed and sim.stopped and sim.active is None
            assert sim.journal.owner != prior.owner
            assert sim.physical_permission()["permission"] == "blocked"
            with sqlite3.connect(path) as db:
                assert db.execute(f"SELECT {','.join(COLUMNS)} FROM {TABLE}").fetchall() == original
            assert sim.journal.acknowledged[values[0]]["position"].hex() == value.hex()
            # The obsolete owner remains fenced; exact preservation is not relaxed.
            stale = TursoJournal(URL, SecretStr(TOKEN))
            stale.owner = prior.owner
            stale.acknowledged = prior.acknowledged.copy()
            try:
                with pytest.raises(JournalFailure) as caught:
                    await stale.save(dict(zip(COLUMNS, (*values[:6], 0.2), strict=True)))
                assert caught.value.category == "ownership"
            finally:
                await stale.close()
        finally:
            if prior is not None:
                await prior.client.aclose()
            await sim.journal.close()
            sim.db.close()

    asyncio.run(run())


@pytest.mark.parametrize("column", ["created", "position"])
@pytest.mark.parametrize("invalid", ["not-a-number", "0.1", None])
def test_lossless_projection_does_not_coerce_invalid_stored_history(remote, column, invalid):
    path, _ = remote

    async def run():
        journal = TursoJournal(URL, SecretStr(TOKEN))
        try:
            await journal.initialize()
            # An untyped hostile schema must not be sanitized into valid history.
            with sqlite3.connect(path) as db:
                db.execute(f"DROP TABLE {TABLE}")
                db.execute(f"CREATE TABLE {TABLE} ({','.join(COLUMNS)})")
                row = ["invalid", "operator", "{}", "completed", "", 1.0, 0.0]
                row[COLUMNS.index(column)] = invalid
                db.execute(f"INSERT INTO {TABLE} VALUES(?,?,?,?,?,?,?)", row)
                db.execute(f"UPDATE {LEASE} SET expires=unixepoch()-1")
            other = TursoJournal(URL, SecretStr(TOKEN))
            try:
                with pytest.raises(JournalFailure):
                    await other.initialize()
            finally:
                await other.close()
        finally:
            await journal.close()

    asyncio.run(run())
