"""FastAPI bridge backend: LiveKit <-> Comni.

Issues client tokens, spawns one full-duplex bridge per room, and exposes
health/session control endpoints for the Flutter app.
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import ServerConfig, comni_config, livekit_config, server_config
from livekit_bridge import LiveKitComniBridge
from prompts import MODES, get_prompt
from tokens import make_token

logger = logging.getLogger("main")
logging.basicConfig(
    level=logging.DEBUG,  # Enable debug for audio flow visibility
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

# room_name -> bridge
bridges: dict[str, LiveKitComniBridge] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backend up — LiveKit=%s, Comni=%s",
                livekit_config.url, comni_config.base_url)
    yield
    # tear down all bridges on shutdown
    await asyncio.gather(*(b.stop() for b in bridges.values()),
                         return_exceptions=True)


app = FastAPI(title="English Tutor Backend", lifespan=lifespan)


# ---- request/response models ----

class SessionRequest(BaseModel):
    mode: str = "free_chat"
    custom_prompt: Optional[str] = None


class SessionResponse(BaseModel):
    room_name: str
    url: str
    token: str  # student token
    mode: str
    tutor_identity: str = "duplex-base"


# ---- endpoints ----

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "livekit_url": livekit_config.url,
        "comni_url": comni_config.base_url,
        "active_sessions": len(bridges),
        "modes": list(MODES.keys()),
    }


@app.get("/modes")
async def list_modes():
    return {"modes": [
        {"id": m.id, "label": m.label, "description": m.description}
        for m in MODES.values()
    ]}


@app.post("/sessions", response_model=SessionResponse)
async def create_session(req: SessionRequest):
    """Create a room, spin up the tutor bridge, return a student token."""
    if req.mode not in MODES and not req.custom_prompt:
        raise HTTPException(400, f"unknown mode '{req.mode}'")

    room_name = f"{livekit_config.room_name_prefix}-{uuid.uuid4().hex[:10]}"
    system_prompt = get_prompt(req.mode, req.custom_prompt)

    bridge = LiveKitComniBridge(room_name, system_prompt)
    bridges[room_name] = bridge

    # run the bridge in the background; log failures and clean up
    task = asyncio.create_task(_run_bridge(room_name, bridge))
    task.add_done_callback(lambda _: bridges.pop(room_name, None))

    # student joins as a normal participant
    token = make_token(
        livekit_config,
        identity=f"student-{uuid.uuid4().hex[:6]}",
        room=room_name,
        name="Student",
    )

    logger.info("Created session room=%s mode=%s", room_name, req.mode)
    return SessionResponse(
        room_name=room_name,
        url=livekit_config.url,
        token=token,
        mode=req.mode,
    )


@app.get("/sessions")
async def list_sessions():
    return {"rooms": list(bridges.keys())}


@app.delete("/sessions/{room_name}")
async def stop_session(room_name: str):
    bridge = bridges.get(room_name)
    if not bridge:
        raise HTTPException(404, "session not found")
    await bridge.stop()
    bridges.pop(room_name, None)
    return {"stopped": room_name}


async def _run_bridge(room_name: str, bridge: LiveKitComniBridge) -> None:
    try:
        await bridge.run()
    except Exception:
        logger.exception("Bridge for room %s crashed", room_name)
    finally:
        bridges.pop(room_name, None)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=server_config.host,
        port=server_config.port,
        log_level=server_config.log_level,
    )
