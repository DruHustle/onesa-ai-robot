"""Inspection records use the real SQL/fenced journal through a synthetic HTTP boundary."""

import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

from robot_api.turso import TABLE
from tests.test_inspection import HASH, PASSWORD, advance_clock, approve, plan
from tests.test_turso import client, config
from tests.test_turso import remote as remote


def sign_in(api):
    response = api.post("/api/v1/auth/login", json={"name": "operator", "password": PASSWORD})
    assert response.status_code == 200
    api.headers["X-CSRF-Token"] = response.json()["csrf"]


def settings(tmp_path):
    return config(tmp_path).model_copy(update={"operator_password_hash": HASH})


def test_inspection_journal_is_event_bounded_and_terminal_evidence_survives_restart(
    remote, tmp_path
):
    path, _ = remote
    with client(settings(tmp_path)) as api:
        sign_in(api)
        assert api.post("/api/v1/reset", json={"password": PASSWORD}).status_code == 200
        detail = plan(api, "discrepancy")
        approve(api, detail)
        advance_clock(api, 0.6)
        api.get("/api/v1/tasks")  # Flush this actual transition before measuring idle ticks.
        sim = api.app.state.sim
        version = api.portal.call(lambda: sim.journal_version)

        def tick_without_transition():
            for _ in range(100):
                sim.active["started"] = time.monotonic() - 0.7
                sim.active["heartbeat"] = time.monotonic()
                sim.tick()
            return sim.journal_version

        assert api.portal.call(tick_without_transition) == version
        advance_clock(api, 6.1)
        final = api.get(f"/api/v1/missions/{detail['id']}").json()
        assert final["record"]["outcome"] == "completed_findings"
        assert api.get("/api/v1/tasks").status_code == 200
        with sqlite3.connect(path) as db:
            original = db.execute(
                f"SELECT proposal FROM {TABLE} WHERE id=?", (detail["id"],)
            ).fetchone()[0]
        assert len(original.encode()) < 16384
        assert json.loads(original)["inspection"] == final["record"]
    with client(settings(tmp_path)) as replacement:
        assert replacement.get(f"/api/v1/missions/{detail['id']}").status_code == 401
        sign_in(replacement)
        assert replacement.get(f"/api/v1/missions/{detail['id']}").json() == final
        assert replacement.get("/api/v1/status").json()["stopped"]
    with sqlite3.connect(path) as db:
        assert (
            db.execute(f"SELECT proposal FROM {TABLE} WHERE id=?", (detail["id"],)).fetchone()[0]
            == original
        )


def test_stop_during_remote_mission_approval_never_activates_and_preserves_interruption(
    remote, tmp_path
):
    _, network = remote
    with client(settings(tmp_path)) as api:
        sign_in(api)
        api.post("/api/v1/reset", json={"password": PASSWORD})
        detail = plan(api)
        network["delay"] = 0.6
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                api.post,
                f"/api/v1/missions/{detail['id']}/approve",
                json={
                    "password": PASSWORD,
                    "expected_plan_sha256": detail["record"]["plan_sha256"],
                },
            )
            for _ in range(100):
                state = api.portal.call(
                    lambda: api.app.state.sim.db.execute(
                        "SELECT state FROM tasks WHERE id=?", (detail["id"],)
                    ).fetchone()[0]
                )
                if state == "running":
                    break
                time.sleep(0.01)
            assert state == "running"
            assert api.portal.call(lambda: api.app.state.sim.active is None)
            assert api.post("/api/v1/stop").status_code == 200
            assert future.result(timeout=5).status_code == 409
        final = api.get(f"/api/v1/missions/{detail['id']}").json()
        assert final["record"]["outcome"] == "interrupted"
        assert final["record"]["events"][-1]["detail"] == "operator_stop"
        assert final["record"]["started_at"] is None
        assert api.get("/api/v1/status").json()["active_task"] is None
