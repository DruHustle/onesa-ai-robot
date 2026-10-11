import asyncio

import pytest

from robot_api import main
from robot_api.security import password_hash


@pytest.mark.parametrize("trickle", [False, True])
def test_incomplete_body_has_total_deadline(tmp_path, monkeypatch, trickle):
    config = main.Settings(
        operator_password_hash=password_hash("synthetic-body-deadline-password"),
        database_path=tmp_path / "body.sqlite3",
    )
    monkeypatch.setattr(main, "REQUEST_BODY_SECONDS", 0.03, raising=False)
    app = main.create_app(config)
    messages = []

    async def receive():
        await asyncio.sleep(0.01 if trickle else 1)
        return {"type": "http.request", "body": b"x", "more_body": True}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/auth/login",
        "query_string": b"",
        "headers": [(b"origin", config.public_origin.encode())],
        "server": ("localhost", 3431),
        "client": ("127.0.0.1", 12345),
    }

    async def run():
        async with asyncio.timeout(0.25):
            await app(scope, receive, send)

    asyncio.run(run())
    assert messages[0]["status"] == 408
    assert dict(messages[0]["headers"])[b"cache-control"] == b"no-store"
