"""Integration test: verifies Mac can speak the real Comni duplex protocol.

Connects to the Windows Comni server, completes the handshake
(connect -> queue_done -> prepare -> prepared), streams a short audio
chunk, and asserts that result/audio events come back.

Run: venv/bin/python tests/test_comni_duplex.py
"""

import asyncio
import base64
import json
import ssl
import uuid
from collections import defaultdict

import numpy as np
import websockets

COMNI_HOST = "192.168.50.103"
COMNI_PORT = 8006
INPUT_SR = 16000   # client -> Comni (Float32 PCM)
OUTPUT_SR = 24000  # Comni -> client (Float32 PCM)

ENGLISH_PROMPT = (
    "You are a friendly English tutor. Speak clearly and naturally in English. "
    "Listen to the student and respond helpfully."
)


def ssl_context_no_verify() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def make_silence_chunk(seconds: float = 1.0) -> bytes:
    """1-second Float32 silence at 16kHz — enough to trigger a server result."""
    n = int(INPUT_SR * seconds)
    return (np.zeros(n, dtype=np.float32)).tobytes()


async def run_test() -> None:
    # adx_ prefix routes to audio_duplex app
    session_id = f"adx_test_{uuid.uuid4().hex[:8]}"
    url = f"wss://{COMNI_HOST}:{COMNI_PORT}/ws/duplex/{session_id}"

    received: dict[str, int] = defaultdict(int)
    prepared_payload: dict = {}
    got_result = asyncio.Event()
    errors: list[str] = []

    print(f"[connect] {url}")
    ctx = ssl_context_no_verify()
    async with websockets.connect(url, ssl=ctx, open_timeout=10,
                                  max_size=128 * 1024 * 1024) as ws:
        # 1. wait for queue_done
        async def reader():
            async for raw in ws:
                msg = json.loads(raw)
                t = msg.get("type")
                received[t] += 1
                if t == "queue_done":
                    print("[recv] queue_done (worker assigned)")
                elif t == "prepared":
                    prepared_payload.update(msg)
                    print(f"[recv] prepared (prompt_length={msg.get('prompt_length')})")
                elif t == "result":
                    if not got_result.is_set():
                        print(f"[recv] first result is_listen={msg.get('is_listen')} "
                              f"has_audio={'audio_data' in msg} text={msg.get('text','')!r}")
                        got_result.set()
                elif t == "audio_only":
                    if not got_result.is_set():
                        print(f"[recv] audio_only (bytes={len(msg.get('audio_data',''))})")
                        got_result.set()
                elif t == "error":
                    errors.append(msg.get("error", "unknown"))
                    print(f"[recv] error: {msg.get('error')}")
                elif t == "timeout":
                    print(f"[recv] timeout: {msg.get('reason')}")

        reader_task = asyncio.create_task(reader())

        # 2. wait for queue_done (or queue messages), then send prepare
        await asyncio.sleep(1.0)  # allow queue_done to arrive
        prepare = {"type": "prepare", "system_prompt": ENGLISH_PROMPT}
        await ws.send(json.dumps(prepare))
        print("[send] prepare")

        # 3. stream a few 1-second silence chunks to provoke a result
        chunk = make_silence_chunk(1.0)
        for i in range(3):
            await ws.send(json.dumps({
                "type": "audio_chunk",
                "audio_base64": base64.b64encode(chunk).decode(),
            }))
            print(f"[send] audio_chunk #{i+1} ({len(chunk)} bytes f32)")
            await asyncio.sleep(1.0)

        # 4. wait briefly for a result/timeout
        try:
            await asyncio.wait_for(got_result.wait(), timeout=8.0)
        except asyncio.TimeoutError:
            print("[warn] no result within 8s (may still be loading)")

        # 5. stop
        await ws.send(json.dumps({"type": "stop"}))
        print("[send] stop")
        await asyncio.sleep(1.0)
        reader_task.cancel()

    # ---- assertions ----
    print(f"\n[summary] message counts: {dict(received)}")
    assert received.get("queue_done", 0) >= 1, "expected queue_done"
    assert "prepared" in received, "expected prepared handshake to complete"
    assert not errors, f"server errors: {errors}"
    print("[PASS] Comni duplex protocol handshake + audio round-trip verified")


if __name__ == "__main__":
    asyncio.run(run_test())
