"""End-to-end integration test: FastAPI backend + LiveKit + Comni.

Creates a session via the FastAPI backend, verifies the bridge starts,
and checks that a LiveKit room is created.

Run: venv/bin/python tests/test_e2e_backend.py
"""

import asyncio
import time
from collections import defaultdict

import httpx


BASE_URL = "http://localhost:8021"


async def test_health():
    """Test that the backend is healthy."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "livekit_url" in data
        assert "comni_url" in data
        print("[PASS] health check")


async def test_modes():
    """Test that the modes endpoint returns expected modes."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/modes")
        assert resp.status_code == 200
        data = resp.json()
        assert "modes" in data
        mode_ids = [m["id"] for m in data["modes"]]
        assert "free_chat" in mode_ids
        assert "interview" in mode_ids
        print(f"[PASS] modes endpoint: {mode_ids}")


async def test_create_session():
    """Test creating a session and verify it starts the bridge."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Create a session
        resp = await client.post(
            f"{BASE_URL}/sessions",
            json={"mode": "free_chat"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "room_name" in data
        assert "token" in data
        assert "url" in data
        room_name = data["room_name"]
        print(f"[PASS] session created: room={room_name}")

        # Give the bridge a moment to start
        await asyncio.sleep(2.0)

        # Check that the session appears in the list
        resp = await client.get(f"{BASE_URL}/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert room_name in data["rooms"]
        print(f"[PASS] session listed: {data['rooms']}")

        # Clean up: stop the session
        resp = await client.delete(f"{BASE_URL}/sessions/{room_name}")
        assert resp.status_code == 200
        print(f"[PASS] session stopped: {room_name}")

        # Verify it's gone
        await asyncio.sleep(0.5)
        resp = await client.get(f"{BASE_URL}/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert room_name not in data["rooms"]
        print("[PASS] session removed from list")


async def test_invalid_mode():
    """Test that invalid mode returns 400."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/sessions",
            json={"mode": "nonexistent_mode"},
        )
        assert resp.status_code == 400
        print("[PASS] invalid mode returns 400")


async def test_custom_prompt():
    """Test creating a session with a custom prompt."""
    custom_prompt = "You are a math tutor. Keep responses brief."
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{BASE_URL}/sessions",
            json={
                "mode": "custom",
                "custom_prompt": custom_prompt,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        room_name = data["room_name"]
        print(f"[PASS] custom prompt session created: room={room_name}")

        # Clean up
        await asyncio.sleep(1.0)
        await client.delete(f"{BASE_URL}/sessions/{room_name}")
        print("[PASS] custom prompt session cleaned up")


async def run_all():
    print("\n=== Backend E2E Tests ===\n")
    await test_health()
    await test_modes()
    await test_create_session()
    await test_invalid_mode()
    await test_custom_prompt()
    print("\n[ALL PASS] Backend E2E tests passed!")


if __name__ == "__main__":
    asyncio.run(run_all())
