"""Configuration for the English Tutor backend.

Comni (Windows inference) and LiveKit (Mac WebRTC SFU) connection settings.
"""

import os
import ssl
from dataclasses import dataclass


@dataclass(frozen=True)
class ComniConfig:
    """Comni inference server (Windows, RTX 3090)."""

    host: str = "192.168.50.103"
    port: int = 8006
    use_ssl: bool = True
    verify_ssl: bool = False  # self-signed certs

    @property
    def base_url(self) -> str:
        scheme = "https" if self.use_ssl else "http"
        return f"{scheme}://{self.host}:{self.port}"

    @property
    def ws_base_url(self) -> str:
        scheme = "wss" if self.use_ssl else "ws"
        return f"{scheme}://{self.host}:{self.port}"

    def duplex_endpoint(self, session_id: str) -> str:
        return f"{self.ws_base_url}/ws/duplex/{session_id}"

    @property
    def ssl_context(self) -> ssl.SSLContext | None:
        if not self.use_ssl:
            return None
        if self.verify_ssl:
            return ssl.create_default_context()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx


@dataclass(frozen=True)
class LiveKitConfig:
    """LiveKit Server (Mac, LAN-only)."""

    host: str = "192.168.50.230"  # Mac's LAN IP
    port: int = 7880
    api_key: str = "API952804082f9cca3d"
    api_secret: str = "XXtJaNOlP7MNsdP5vLq5N6XwBHFwmkD1/waFPwt3sFo="
    room_name_prefix: str = "duplex-base"

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"


@dataclass(frozen=True)
class AudioConfig:
    """Sample-rate contract across the pipeline."""

    comni_input_sample_rate: int = 16000   # client -> Comni
    comni_output_sample_rate: int = 24000  # Comni -> client
    livekit_sample_rate: int = 48000       # LiveKit wire format


@dataclass(frozen=True)
class ServerConfig:
    """FastAPI server."""

    host: str = "0.0.0.0"
    port: int = 8021
    log_level: str = "info"


# Comni WebSocket event types (real protocol)
class ComniEventType:
    # client -> server
    PREPARE = "prepare"
    AUDIO_CHUNK = "audio_chunk"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"

    # server -> client
    QUEUE_DONE = "queue_done"
    PREPARED = "prepared"
    RESULT = "result"
    AUDIO_ONLY = "audio_only"
    ERROR = "error"


# Singletons (env overrides for deployment flexibility)
comni_config = ComniConfig(
    host=os.getenv("COMNI_HOST", "192.168.50.103"),
    port=int(os.getenv("COMNI_PORT", "8006")),
)
livekit_config = LiveKitConfig(
    host=os.getenv("LIVEKIT_HOST", "192.168.50.230"),
    port=int(os.getenv("LIVEKIT_PORT", "7880")),
    api_key=os.getenv("LIVEKIT_API_KEY", "API952804082f9cca3d"),
    api_secret=os.getenv("LIVEKIT_API_SECRET",
                         "XXtJaNOlP7MNsdP5vLq5N6XwBHFwmkD1/waFPwt3sFo="),
)
audio_config = AudioConfig()
server_config = ServerConfig()
