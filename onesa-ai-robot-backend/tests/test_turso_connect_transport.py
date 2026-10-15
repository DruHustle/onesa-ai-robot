"""Exercise HTTPX's real connection-retry boundary with an isolated fake socket."""

import asyncio
import json

import httpcore
import pytest
from pydantic import SecretStr

from robot_api.turso import JournalFailure, TursoJournal


class Stream(httpcore.AsyncNetworkStream):
    def __init__(self, read_error=None, keep_alive=False):
        body = json.dumps(
            {
                "results": [
                    {
                        "type": "ok",
                        "response": {"type": "execute", "result": {"cols": [], "rows": []}},
                    },
                    {"type": "ok", "response": {"type": "close"}},
                ]
            }
        ).encode()
        self.response = (
            b"HTTP/1.1 200 OK\r\nContent-Length: "
            + str(len(body)).encode()
            + b"\r\nConnection: close\r\n\r\n"
            + body
        )
        if keep_alive:
            self.response = self.response.replace(b"Connection: close", b"Connection: keep-alive")
        self.template = self.response
        self.written = bytearray()
        self.write_error = (
            read_error if read_error in {httpcore.WriteError, httpcore.WriteTimeout} else None
        )
        self.read_error = read_error if self.write_error is None else None

    async def read(self, max_bytes, timeout=None):
        if self.write_error is httpcore.WriteError:
            # HTTPcore may try to read an early server response after WriteError.
            # Model an actually broken connection rather than a valid 200 reply.
            raise httpcore.ReadError("synthetic private connection closed")
        if self.read_error:
            raise self.read_error("synthetic private failure detail")
        data, self.response = self.response[:max_bytes], self.response[max_bytes:]
        return data

    async def write(self, buffer, timeout=None):
        if buffer.startswith(b"POST "):
            self.response = self.template
        self.written.extend(buffer)
        if self.write_error:
            raise self.write_error("synthetic private write detail")

    async def aclose(self):
        pass

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        return self

    def get_extra_info(self, info):
        return None


class Backend(httpcore.AsyncNetworkBackend):
    def __init__(self, error, failures, stream):
        self.error, self.failures, self.stream = error, failures, stream
        self.connections = 0
        self.timeouts = []

    async def connect_tcp(self, host, port, timeout=None, **kwargs):
        self.connections += 1
        self.timeouts.append(timeout)
        if self.connections <= self.failures:
            raise self.error("synthetic private connection detail")
        return self.stream

    async def sleep(self, seconds):
        assert seconds == 0


@pytest.mark.parametrize("error", [httpcore.ConnectError, httpcore.ConnectTimeout])
def test_one_pre_request_connect_failure_sends_the_statement_once(error):
    async def run():
        journal = TursoJournal("libsql://synthetic.example.turso.io", SecretStr("synthetic"))
        stream = Stream()
        backend = Backend(error, 1, stream)
        journal.client._transport._pool._network_backend = backend
        try:
            assert await journal.execute("SELECT 1") == []
            assert backend.connections == 2
            assert backend.timeouts == [1.0, 1.0]
            assert bytes(stream.written).count(b"POST /v2/pipeline HTTP/1.1") == 1
        finally:
            await journal.client.aclose()

    asyncio.run(run())


def test_journal_does_not_reuse_a_connection_even_if_server_advertises_keepalive():
    class FreshBackend(Backend):
        def __init__(self):
            super().__init__(httpcore.ConnectError, 0, None)
            self.streams = []

        async def connect_tcp(self, host, port, timeout=None, **kwargs):
            self.connections += 1
            stream = Stream(keep_alive=True)
            self.streams.append(stream)
            return stream

    async def run():
        journal = TursoJournal("libsql://synthetic.example.turso.io", SecretStr("synthetic"))
        backend = FreshBackend()
        journal.client._transport._pool._network_backend = backend
        try:
            assert await journal.execute("SELECT 1") == []
            assert await journal.execute("SELECT 1") == []
            assert backend.connections == 2
            assert len(backend.streams) == 2
            assert all(
                bytes(stream.written).count(b"POST /v2/pipeline HTTP/1.1") == 1
                for stream in backend.streams
            )
        finally:
            await journal.client.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("error", [httpcore.ConnectError, httpcore.ConnectTimeout])
def test_connect_retry_is_bounded_and_never_sends_when_it_cannot_connect(error):
    async def run():
        journal = TursoJournal("libsql://synthetic.example.turso.io", SecretStr("synthetic"))
        stream = Stream()
        backend = Backend(error, 2, stream)
        journal.client._transport._pool._network_backend = backend
        try:
            with pytest.raises(JournalFailure) as caught:
                await journal.execute("SELECT 1", phase="task_save")
            assert caught.value.transport_kind == error.__name__
            assert backend.connections == 2
            assert not stream.written
            assert "private" not in str(caught.value)
        finally:
            await journal.client.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "error",
    [
        httpcore.ReadError,
        httpcore.ReadTimeout,
        httpcore.WriteError,
        httpcore.WriteTimeout,
        httpcore.RemoteProtocolError,
    ],
)
def test_ambiguous_after_send_errors_never_reconnect_or_resend(error):
    async def run():
        journal = TursoJournal("libsql://synthetic.example.turso.io", SecretStr("synthetic"))
        stream = Stream(read_error=error)
        backend = Backend(httpcore.ConnectError, 0, stream)
        journal.client._transport._pool._network_backend = backend
        try:
            with pytest.raises(JournalFailure) as caught:
                await journal.execute("SELECT 1", phase="task_save")
            expected_kind = "ReadError" if error is httpcore.WriteError else error.__name__
            assert caught.value.transport_kind == expected_kind
            assert backend.connections == 1
            assert bytes(stream.written).count(b"POST /v2/pipeline HTTP/1.1") == 1
            assert "private" not in str(caught.value)
        finally:
            await journal.client.aclose()

    asyncio.run(run())
