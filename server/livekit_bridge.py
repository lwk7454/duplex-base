"""Full-duplex audio bridge between a LiveKit room and the Comni server.

The bridge joins a LiveKit room as the "tutor" participant, subscribes to the
student's microphone (resampled to 16kHz float32 for Comni), and publishes
Comni's audio reply (24kHz float32) back to the room. Text/transcripts from
Comni are forwarded as LiveKit data messages for the UI overlay.

PCM formats:
  - LiveKit wire: int16 interleaved (16kHz mic capture, 24kHz AI playback)
  - Comni wire:   float32 (16kHz in, 24kHz out)
"""

import asyncio
import base64
import json
import logging
import time
import uuid

import numpy as np
from livekit import rtc

from comni_client import ComniClient, ComniResult
from config import ComniConfig, LiveKitConfig, comni_config, livekit_config
from tokens import make_token

logger = logging.getLogger("livekit_bridge")

TUTOR_IDENTITY = "duplex-base"
DATA_TOPIC = "tutor-data"

INT16_MAX = 32767.0
INT16_SCALE = 32768.0  # symmetric divisor: -32768 -> -1.0 exactly


class LiveKitComniBridge:
    """One LiveKit room <-> one Comni duplex session."""

    def __init__(
        self,
        room_name: str,
        system_prompt: str,
        comni_cfg: ComniConfig = comni_config,
        livekit_cfg: LiveKitConfig = livekit_config,
    ):
        self.room_name = room_name
        self.system_prompt = system_prompt
        self.comni_cfg = comni_cfg
        self.livekit_cfg = livekit_cfg

        self._room: rtc.Room | None = None
        self._comni: ComniClient | None = None
        self._audio_source: rtc.AudioSource | None = None
        self._student_sid: str | None = None
        self._tasks: list[asyncio.Task] = []
        self._closed = asyncio.Event()

    async def run(self) -> None:
        """Connect to LiveKit + Comni and pump audio until the room empties."""
        self._room = rtc.Room()

        # Wire Comni callbacks before connecting
        self._comni = ComniClient(
            config=self.comni_cfg,
            system_prompt=self.system_prompt,
        )
        self._comni.callbacks.on_result = self._on_comni_result
        self._comni.callbacks.on_state = self._on_comni_state

        @self._room.on("participant_connected")
        def _on_participant(participant: rtc.RemoteParticipant):
            asyncio.create_task(self._subscribe_student(participant))

        @self._room.on("track_published")
        def _on_track_published(participant: rtc.RemoteParticipant, track_publication: rtc.RemoteTrackPublication):
            if self._student_sid == participant.sid:
                logger.info("Student published track: %s", track_publication.sid)
                # Try subscribing again in case we missed it
                asyncio.create_task(self._subscribe_student(participant))

        @self._room.on("participant_disconnected")
        def _on_disconnect(participant: rtc.RemoteParticipant):
            logger.info("Participant left: %s", participant.identity)
            if self._student_sid == participant.sid:
                asyncio.create_task(self.stop())

        # 1. Join room
        token = make_token(
            self.livekit_cfg,
            identity=TUTOR_IDENTITY,
            room=self.room_name,
            name="English Tutor",
            can_publish=True,
        )
        logger.info("Joining LiveKit room %s ...", self.room_name)
        await self._room.connect(self.livekit_cfg.url, token)
        logger.info("Joined room; local sid=%s", self._room.local_participant.sid)

        # 2. Publish AI audio track (24kHz to match Comni output)
        self._audio_source = rtc.AudioSource(24_000, 1)
        track = rtc.LocalAudioTrack.create_audio_track("tutor-voice", self._audio_source)
        await self._room.local_participant.publish_track(track, rtc.TrackPublishOptions())
        logger.info("Published AI audio track")

        # 3. Connect Comni (handshake: queue_done -> prepare -> prepared)
        await self._comni.connect()
        logger.info("Comni session ready")

        # 4. Subscribe to any student already in the room
        for participant in self._room.remote_participants.values():
            await self._subscribe_student(participant)

        # 5. Run until closed
        await self._closed.wait()

    async def stop(self) -> None:
        if self._closed.is_set():
            return
        logger.info("Stopping bridge for room %s", self.room_name)
        self._closed.set()
        for t in self._tasks:
            t.cancel()
        if self._comni:
            await self._comni.close()
        if self._room:
            await self._room.disconnect()

    # ---- student audio -> Comni ----

    async def _subscribe_student(self, participant: rtc.RemoteParticipant) -> None:
        if self._student_sid is not None and self._student_sid != participant.sid:
            return  # single student per session
        self._student_sid = participant.sid
        logger.info("Subscribing to student: %s", participant.identity)

        # Find the microphone track publication
        mic_pub = None
        for pub in participant.track_publications.values():
            if pub.source == rtc.TrackSource.SOURCE_MICROPHONE:
                mic_pub = pub
                logger.info("Found student microphone publication: %s", pub.sid)
                break

        if not mic_pub:
            logger.debug("No microphone publication found yet for student %s (will retry on track_published)", participant.identity)
            return

        # Check if we've already set up the audio stream
        if any(t.get_name() == "_pump_student_audio" for t in self._tasks if not t.done()):
            logger.debug("Audio stream already set up for student %s", participant.identity)
            return

        # Subscribe to the track if not already subscribed
        if not mic_pub.subscribed:
            logger.info("Subscribing to track %s", mic_pub.sid)
            await mic_pub.set_subscribed(True)

        # AudioStream resamples to 16kHz int16 for Comni input
        stream = rtc.AudioStream.from_participant(
            participant=participant,
            track_source=rtc.TrackSource.SOURCE_MICROPHONE,
            sample_rate=16_000,
            num_channels=1,
        )
        logger.info("Created AudioStream for student audio")
        task = asyncio.create_task(self._pump_student_audio(stream), name="_pump_student_audio")
        self._tasks.append(task)

    async def _pump_student_audio(self, stream: rtc.AudioStream) -> None:
        """Forward student audio frames (int16 16kHz) to Comni as float32."""
        logger.info("Starting audio pump for student")
        frame_count = 0
        try:
            async for event in stream:
                frame = event.frame  # AudioFrameEvent has a 'frame' attribute
                logger.debug("Received audio frame from LiveKit: %d bytes", len(frame.data))
                if self._closed.is_set() or not self._comni or not self._comni.is_ready:
                    logger.debug("Skipping frame: closed=%s, comni=%s, ready=%s",
                                 self._closed.is_set(), self._comni is not None,
                                 self._comni.is_ready if self._comni else False)
                    continue
                pcm_f32 = int16_to_float32(frame.data)
                await self._comni.send_audio(pcm_f32)
                frame_count += 1
                if frame_count % 10 == 0:  # Log every 10 frames
                    logger.info("Forwarded %d audio frames to Comni", frame_count)
        except Exception as e:
            logger.exception("Audio pump error: %s", e)
        finally:
            logger.info("Audio pump ended after %d frames", frame_count)

    # ---- Comni -> room ----

    async def _on_comni_result(self, result: ComniResult) -> None:
        logger.info("Comni result: is_listen=%s, text=%r, has_audio=%s",
                     result.is_listen, result.text[:50] if result.text else "", bool(result.audio))

        # Publish audio reply (24kHz float32 -> int16 -> AudioSource)
        if result.audio and self._audio_source and not self._closed.is_set():
            pcm_i16 = float32_to_int16(result.audio)
            frame = rtc.AudioFrame(
                data=pcm_i16.tobytes(),
                sample_rate=24_000,
                num_channels=1,
                samples_per_channel=len(pcm_i16),
            )
            await self._audio_source.capture_frame(frame)
            logger.debug("Published audio frame: %d samples", len(pcm_i16))

        # Forward spoken text + transcripts to the UI via data channel
        if result.text and self._room:
            await self._send_data({
                "kind": "tutor_text",
                "text": result.text,
                "is_listen": result.is_listen,
                "ts": time.time(),
            })

    async def _on_comni_state(self, state: str, payload: dict) -> None:
        if state in ("disconnected", "stopped", "timeout"):
            logger.warning("Comni %s — stopping room", state)
            await self._send_data({"kind": "state", "state": state})
            await self.stop()

    async def _send_data(self, payload: dict) -> None:
        if not self._room:
            return
        try:
            await self._room.local_participant.publish_data(
                json.dumps(payload).encode(),
                reliable=True,
                topic=DATA_TOPIC,
            )
        except Exception:
            logger.debug("data publish failed", exc_info=True)


# ---- PCM helpers ----

def int16_to_float32(data: bytes | memoryview) -> bytes:
    """LiveKit int16 PCM -> Comni float32 PCM."""
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / INT16_SCALE
    return samples.tobytes()


def float32_to_int16(data: bytes) -> np.ndarray:
    """Comni float32 PCM -> LiveKit int16 PCM (32768-scaled, clipped)."""
    samples = np.frombuffer(data, dtype=np.float32)
    return np.clip(samples * INT16_SCALE, -32768, 32767).astype(np.int16)
