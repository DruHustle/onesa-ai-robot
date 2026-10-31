"""Whole-body supervision remains responsive while a real fenced journal is enabled."""

from concurrent.futures import ThreadPoolExecutor

from tests.test_humanoid import HASH, sign_in, start_motion
from tests.test_turso import client, config
from tests.test_turso import remote as remote


def test_dedicated_heartbeat_and_stop_bypass_queued_journal_mutations(remote, tmp_path):
    settings = config(tmp_path).model_copy(
        update={"operator_password_hash": HASH, "heartbeat_seconds": 10}
    )
    with client(settings) as api:
        sign_in(api)
        command = start_motion(api)
        sim = api.app.state.sim

        async def hold_mutations():
            await sim.mutation_lock.acquire()

        api.portal.call(hold_mutations)
        try:
            # A blocked acknowledgement/confirmation owns this same lock in the
            # real middleware. Supervision and Stop must finish before it releases.
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    api.post, "/api/v1/humanoid/heartbeat", json={"command_id": command}
                )
                try:
                    assert future.result(timeout=2).status_code == 200
                finally:
                    # Unblock on assertion failure as well; never strand teardown.
                    if not future.done():
                        api.portal.call(sim.mutation_lock.release)
                stopped = executor.submit(api.post, "/api/v1/stop", json={})
                try:
                    assert stopped.result(timeout=2).status_code == 200
                finally:
                    if not stopped.done() and sim.mutation_lock.locked():
                        api.portal.call(sim.mutation_lock.release)
            assert api.portal.call(lambda: sim.humanoid.active) is None
            assert api.portal.call(lambda: sim.stopped)
        finally:
            if sim.mutation_lock.locked():
                api.portal.call(sim.mutation_lock.release)
