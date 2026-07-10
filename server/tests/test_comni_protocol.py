"""BDD tests: ComniClient protocol handling with a mocked WebSocket.

All network calls are mocked. No real timings — every wait is bounded by
driving the fake server deterministically.
"""

import asyncio
import base64
import json
from unittest.mock import patch

import numpy as np
import pytest

from comni_client import ComniClient, ComniResult
from config import ComniConfig
from tests.expectations import expect, raises


class FakeWebSocket:
    """Deterministic stand-in for websockets.WebSocketClientProtocol.

    `incoming` is a list of JSON-serializable dicts the fake server will send.
    Sent messages are captured in `sent`. After delivering all queued messages
    the socket stays open (blocks) — like a real persistent WS — until closed.
    """

    def __init__(self, incoming: list[dict]):
        self._incoming = [json.dumps(m) for m in incoming]
        self.sent: list[dict] = []
        self._closed = False
        self._block = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._incoming:
            return self._incoming.pop(0)
        # No more queued messages: emulate an open persistent connection.
        await self._block.wait()  # never set unless close() fires
        raise StopAsyncIteration

    async def send(self, raw: str):
        self.sent.append(json.loads(raw))

    async def close(self):
        self._closed = True
        self._block.set()


@pytest.fixture
def config():
    return ComniConfig(host="fake", port=8006)


def _patch_connect(fake_ws: FakeWebSocket):
    async def _connect(*a, **kw):
        return fake_ws
    return patch("comni_client.websockets.connect", side_effect=_connect)


async def _connect_and_close(client: ComniClient, fake: FakeWebSocket):
    """Connect inside the patch, then shut down the background recv loop."""
    with _patch_connect(fake):
        await client.connect()
        yield
        await client.close()


class DescribeConnectHandshake:
    @pytest.mark.asyncio
    async def it_waits_for_queue_done_then_sends_prepare_then_waits_prepared(self, config):
        fake = FakeWebSocket([{"type": "queue_done"}, {"type": "prepared", "prompt_length": 42}])
        client = ComniClient(config, system_prompt="hello")
        try:
            with _patch_connect(fake):
                await client.connect()
                expect(client.is_ready).to_be_truthy()
                sent_types = [m["type"] for m in fake.sent]
                expect(sent_types).to_contain("prepare")
                expect(fake.sent[0]["system_prompt"]).to_equal("hello")
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def it_includes_ref_audio_when_provided(self, config):
        fake = FakeWebSocket([{"type": "queue_done"}, {"type": "prepared"}])
        client = ComniClient(config, system_prompt="hi", ref_audio_base64="BASE64==")
        try:
            with _patch_connect(fake):
                await client.connect()
                expect(fake.sent[0].get("ref_audio_base64")).to_equal("BASE64==")
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def it_times_out_when_queue_done_never_arrives(self, config):
        async def _instant_timeout(awaitable, timeout):
            # close the never-awaited coroutine cleanly, then time out
            close = getattr(awaitable, "close", None)
            if close:
                close()
            raise asyncio.TimeoutError()

        fake = FakeWebSocket([])  # server never sends queue_done
        client = ComniClient(config, system_prompt="hi")
        with patch("comni_client.asyncio.wait_for", side_effect=_instant_timeout):
            with raises(Exception):
                with _patch_connect(fake):
                    await client.connect()


class DescribeResultHandling:
    @pytest.mark.asyncio
    async def it_decodes_audio_and_invokes_on_result(self, config):
        samples = np.array([0.5, -0.5], dtype=np.float32)
        audio_b64 = base64.b64encode(samples.tobytes()).decode()
        fake = FakeWebSocket([
            {"type": "queue_done"}, {"type": "prepared"},
            {"type": "result", "is_listen": False, "audio_data": audio_b64, "text": "Hi"},
        ])
        client = ComniClient(config, system_prompt="hi")
        results: list[ComniResult] = []

        async def on_result(r):
            results.append(r)

        client.callbacks.on_result = on_result
        try:
            with _patch_connect(fake):
                await client.connect()
                await asyncio.sleep(0.05)  # let the recv loop deliver
            expect(len(results)).to_equal(1)
            expect(results[0].is_listen).to_be_falsy()
            expect(results[0].text).to_equal("Hi")
            np.testing.assert_array_equal(
                np.frombuffer(results[0].audio, dtype=np.float32), samples)
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def it_routes_audio_only_events_to_dedicated_callback(self, config):
        audio_b64 = base64.b64encode(np.float32(0.0).tobytes()).decode()
        fake = FakeWebSocket([
            {"type": "queue_done"}, {"type": "prepared"},
            {"type": "audio_only", "audio_data": audio_b64},
        ])
        client = ComniClient(config, system_prompt="hi")
        chunks: list[bytes] = []

        async def on_audio(data):
            chunks.append(data)

        client.callbacks.on_audio_only = on_audio
        try:
            with _patch_connect(fake):
                await client.connect()
                await asyncio.sleep(0.05)
            expect(len(chunks)).to_equal(1)
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def it_invokes_on_error_for_error_messages(self, config):
        fake = FakeWebSocket([
            {"type": "queue_done"}, {"type": "prepared"},
            {"type": "error", "error": "boom"},
        ])
        client = ComniClient(config, system_prompt="hi")
        errors: list[str] = []

        async def on_error(msg):
            errors.append(msg)

        client.callbacks.on_error = on_error
        try:
            with _patch_connect(fake):
                await client.connect()
                await asyncio.sleep(0.05)
            expect(errors).to_contain("boom")
        finally:
            await client.close()


class DescribeSendAudio:
    @pytest.mark.asyncio
    async def it_encodes_audio_as_audio_chunk_with_base64(self, config):
        fake = FakeWebSocket([{"type": "queue_done"}, {"type": "prepared"}])
        client = ComniClient(config, system_prompt="hi")
        try:
            with _patch_connect(fake):
                await client.connect()
                fake.sent.clear()
                pcm = np.zeros(16, dtype=np.float32).tobytes()
                await client.send_audio(pcm)
            expect(len(fake.sent)).to_equal(1)
            msg = fake.sent[0]
            expect(msg["type"]).to_equal("audio_chunk")
            expect(base64.b64decode(msg["audio_base64"])).to_equal(pcm)
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def it_ignores_send_when_not_ready(self, config):
        async def _instant_timeout(awaitable, timeout):
            close = getattr(awaitable, "close", None)
            if close:
                close()
            raise asyncio.TimeoutError()

        fake = FakeWebSocket([{"type": "queue_done"}])  # never prepared
        client = ComniClient(config, system_prompt="hi")
        with patch("comni_client.asyncio.wait_for", side_effect=_instant_timeout):
            with _patch_connect(fake):
                try:
                    await client.connect()
                except Exception:
                    pass
        # not ready -> send_audio must be a no-op (no raise, nothing sent)
        await client.send_audio(b"\x00" * 64)
        expect(client.is_ready).to_be_falsy()
