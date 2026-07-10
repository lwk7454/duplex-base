"""End-to-end audio pipeline test: LiveKit client -> Comni -> response.

Creates a session, joins the LiveKit room as a student, sends test audio,
and verifies the tutor responds with audio.

This is a manual integration test — run with:
  venv/bin/python tests/test_e2e_audio.py

Requires:
  - LiveKit Server running on localhost:7880
  - Comni running on 192.168.50.103:8006
  - Backend running on localhost:8021
"""

import asyncio
import base64
import json
import time
import uuid
from pathlib import Path

import httpx
import numpy as np
from livekit import rtc

# Backend URL
BACKEND_URL = "http://localhost:8021"

# Generate 1 second of silence at 16kHz int16 (what we'd send to LiveKit)
def make_silence_ms(seconds: float = 1.0) -> bytes:
    n_samples = int(16000 * seconds)
    return np.zeros(n_samples, dtype=np.int16).tobytes()


async def test_audio_pipeline():
    """Full end-to-end audio test through the pipeline."""

    print("\n=== E2E Audio Pipeline Test ===\n")

    # 1. Create a session via backend
    print("[1/5] Creating session...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{BACKEND_URL}/sessions",
            json={"mode": "free_chat"},
        )
        if resp.status_code != 200:
            print(f"[FAIL] Session creation failed: {resp.status_code}")
            return False
        data = resp.json()
        room_name = data["room_name"]
        token = data["token"]
        livekit_url = data["url"]
        print(f"[OK] Session created: room={room_name}")

    # 2. Connect to LiveKit room as student
    print("[2/5] Connecting to LiveKit room...")
    room = rtc.Room()

    audio_received = asyncio.Event()
    audio_frames = []
    stop_sending = asyncio.Event()

    @room.on("participant_connected")
    def on_participant_connected(p: rtc.RemoteParticipant):
        print(f"[OK] Tutor joined: {p.identity}")
        # Subscribe to tutor's audio
        for track_publication in p.track_publications.values():
            if track_publication.track:
                asyncio.create_task(subscribe_tutor_audio(track_publication, audio_frames, audio_received))

    async def subscribe_tutor_audio(track_pub, audio_frames_list, event):
        stream = rtc.AudioStream.from_track(track=track_pub.track)
        print("[OK] Subscribed to tutor audio")
        async for evt in stream:
            audio_frames_list.append(evt.frame)
            if not event.is_set():
                print(f"[OK] Received audio frame: {len(evt.frame.data)} bytes")
                event.set()
                break  # Got at least one frame

    await room.connect(livekit_url, token)
    print(f"[OK] Connected as student: {room.local_participant.identity}")

    # 3. Publish student microphone
    print("[3/5] Publishing student microphone...")
    audio_source = rtc.AudioSource(16000, 1)
    track = rtc.LocalAudioTrack.create_audio_track("student-mic", audio_source)
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await room.local_participant.publish_track(track, options)
    print("[OK] Student microphone published")

    # 4. Send audio continuously in background while waiting for response
    print("[4/5] Starting continuous audio stream...")
    silence = make_silence_ms(1.0)

    async def send_audio_loop():
        frame_count = 0
        while not stop_sending.is_set() and not audio_received.is_set():
            frame = rtc.AudioFrame(
                data=silence,
                sample_rate=16000,
                num_channels=1,
                samples_per_channel=len(silence) // 2,  # int16 = 2 bytes per sample
            )
            await audio_source.capture_frame(frame)
            frame_count += 1
            if frame_count % 5 == 0:
                print(f"[INFO] Sent {frame_count} audio frames")
            await asyncio.sleep(1.0)
        print(f"[INFO] Stopped sending audio after {frame_count} frames")

    send_task = asyncio.create_task(send_audio_loop())
    print("[OK] Sending audio continuously...")

    # 5. Wait for audio response
    print("[5/5] Waiting for audio response...")
    try:
        await asyncio.wait_for(audio_received.wait(), timeout=20.0)
        print(f"[PASS] Received audio response! Got {len(audio_frames)} frames")
        success = True
    except asyncio.TimeoutError:
        print("[FAIL] No audio received within 20 seconds")
        success = False
    finally:
        # Stop sending audio
        stop_sending.set()
        if not send_task.done():
            send_task.cancel()

        # Clean up
        await room.disconnect()

        # Stop the session
        async with httpx.AsyncClient() as client:
            await client.delete(f"{BACKEND_URL}/sessions/{room_name}")
        print("[OK] Session cleaned up")

    return success


async def main():
    try:
        success = await test_audio_pipeline()
        if success:
            print("\n[PASS] E2E audio pipeline test passed!")
        else:
            print("\n[FAIL] E2E audio pipeline test failed!")
            exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
