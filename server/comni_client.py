"""Async WebSocket client for the Comni inference server.

Speaks the real Comni audio-duplex protocol (reverse-engineered from
the official frontend `duplex-session.js`):

  1. connect  -> wss://host:8006/ws/duplex/{session_id}   (adx_ prefix)
  2. recv     -> queue_done   (worker assigned)
  3. send     -> prepare {system_prompt, ...}
  4. recv     -> prepared     (handshake complete, prompt tokenized)
  5. send     -> audio_chunk {audio_base64}   (16kHz Float32 PCM)
  6. recv     -> result {is_listen, audio_data, text, ...} | audio_only
  7. send     -> stop / pause / resume

Audio formats:
  - input  (client -> Comni): 16kHz mono Float32 PCM, base64
  - output (Comni -> client): 24kHz mono Float32 PCM, base64
"""

import asyncio
import base64
import json
import logging
import ssl
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

import websockets

from config import ComniConfig, ComniEventType

logger = logging.getLogger("comni_client")

# Sample rates agreed by the protocol
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 24000


@dataclass
class ComniResult:
    """A `result` event from Comni (one decode step, ~0.5s)."""

    is_listen: bool = False
    text: str = ""
    audio: Optional[bytes] = None  # 24kHz Float32 PCM
    end_of_turn: bool = False
    kv_cache_length: Optional[int] = None


@dataclass
class ComniCallbacks:
    """Handlers for Comni events. Each is async."""

    on_prepared: Optional[Callable[[dict], Awaitable[None]]] = None
    on_result: Optional[Callable[[ComniResult], Awaitable[None]]] = None
    on_audio_only: Optional[Callable[[bytes], Awaitable[None]]] = None
    on_state: Optional[Callable[[str, dict], Awaitable[None]]] = None  # type, payload
    on_error: Optional[Callable[[str], Awaitable[None]]] = None


class ComniClient:
    """Full-duplex Comni session over a single WebSocket."""

    def __init__(
        self,
        config: ComniConfig,
        system_prompt: str,
        session_id: Optional[str] = None,
        ref_audio_base64: Optional[str] = None,
    ):
        self.config = config
        self.system_prompt = system_prompt
        self.ref_audio_base64 = ref_audio_base64

        # adx_ prefix routes to the audio_duplex app on the gateway
        self.session_id = session_id or f"adx_{uuid.uuid4().hex[:12]}"
        self.callbacks = ComniCallbacks()

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._queue_done = asyncio.Event()
        self._prepared = asyncio.Event()
        self._closed = asyncio.Event()

    @property
    def is_ready(self) -> bool:
        return self._prepared.is_set() and not self._closed.is_set()

    async def connect(self) -> None:
        """Connect, wait for queue_done, send prepare, wait for prepared."""
        url = self.config.duplex_endpoint(self.session_id)
        logger.info("Connecting to Comni: %s", url)

        self._ws = await websockets.connect(
            url,
            ssl=self.config.ssl_context,
            open_timeout=10,
            max_size=128 * 1024 * 1024,
        )
        self._recv_task = asyncio.create_task(self._recv_loop())

        try:
            await asyncio.wait_for(self._queue_done.wait(), timeout=30.0)
            await self._send_prepare()
            await asyncio.wait_for(self._prepared.wait(), timeout=60.0)
        except Exception:
            await self.close()
            raise

        logger.info("Comni session %s ready", self.session_id)

    async def send_audio(self, pcm_f32_16k: bytes) -> None:
        """Send a 16kHz Float32 PCM audio chunk."""
        if not self.is_ready:
            return
        await self._send({
            "type": ComniEventType.AUDIO_CHUNK,
            "audio_base64": base64.b64encode(pcm_f32_16k).decode("ascii"),
        })

    async def stop(self) -> None:
        if self._ws and not self._closed.is_set():
            try:
                await self._send({"type": ComniEventType.STOP})
            except Exception:
                pass

    async def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        if self._recv_task:
            self._recv_task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        logger.info("Comni session %s closed", self.session_id)

    # ---- internals ----

    async def _send_prepare(self) -> None:
        msg: dict[str, Any] = {
            "type": ComniEventType.PREPARE,
            "system_prompt": self.system_prompt,
        }
        if self.ref_audio_base64:
            msg["ref_audio_base64"] = self.ref_audio_base64
        await self._send(msg)
        logger.debug("Sent prepare for %s", self.session_id)

    async def _recv_loop(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    await self._handle(json.loads(raw))
                except json.JSONDecodeError:
                    logger.warning("Non-JSON frame from Comni")
                except Exception as e:
                    logger.exception("Error handling Comni message: %s", e)
        except websockets.ConnectionClosed:
            logger.info("Comni WebSocket closed")
        except Exception as e:
            logger.exception("Comni recv loop error: %s", e)
        finally:
            self._closed.set()
            if self.callbacks.on_state:
                await self.callbacks.on_state("disconnected", {})

    async def _handle(self, msg: dict[str, Any]) -> None:
        mtype = msg.get("type")

        if mtype == ComniEventType.QUEUE_DONE:
            self._queue_done.set()
        elif mtype == ComniEventType.PREPARED:
            self._prepared.set()
            if self.callbacks.on_prepared:
                await self.callbacks.on_prepared(msg)
        elif mtype == ComniEventType.RESULT:
            await self._handle_result(msg)
        elif mtype == ComniEventType.AUDIO_ONLY:
            audio = self._decode_audio(msg.get("audio_data"))
            if audio and self.callbacks.on_audio_only:
                await self.callbacks.on_audio_only(audio)
        elif mtype == ComniEventType.ERROR:
            err = msg.get("error", "unknown")
            logger.error("Comni error: %s", err)
            if self.callbacks.on_error:
                await self.callbacks.on_error(err)
        elif mtype in ("stopped", "timeout"):
            reason = msg.get("reason", mtype)
            if self.callbacks.on_state:
                await self.callbacks.on_state(mtype, msg)
            logger.info("Comni %s: %s", mtype, reason)
            self._closed.set()
        elif mtype in ("paused", "resumed", "queued", "queue_update"):
            if self.callbacks.on_state:
                await self.callbacks.on_state(mtype, msg)
        else:
            logger.debug("Unhandled Comni message: %s", mtype)

    async def _handle_result(self, msg: dict[str, Any]) -> None:
        result = ComniResult(
            is_listen=bool(msg.get("is_listen", False)),
            text=msg.get("text", "") or "",
            audio=self._decode_audio(msg.get("audio_data")),
            end_of_turn=bool(msg.get("end_of_turn", False)),
            kv_cache_length=msg.get("kv_cache_length"),
        )
        if self.callbacks.on_result:
            await self.callbacks.on_result(result)

    @staticmethod
    def _decode_audio(b64: Optional[str]) -> Optional[bytes]:
        if not b64:
            return None
        try:
            return base64.b64decode(b64)
        except Exception:
            logger.warning("Failed to decode audio payload")
            return None

    async def _send(self, msg: dict[str, Any]) -> None:
        if self._ws and not self._closed.is_set():
            await self._ws.send(json.dumps(msg))
