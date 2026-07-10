# Full-Duplex Voice AI Playground

## Project Goal
Build a full-duplex conversation LLM platform using MiniCPM-o 4.5 running on a local RTX 3090. The English tutor is one application on top — the core is a reusable real-time voice conversation platform.

## Architecture

```
[Flutter App]                        [Mac (dev + serving)]           [Windows RTX 3090]
  ├── LiveKit SDK (WebRTC)           ├── LiveKit Server (:7880)      ├── Comni (llama.cpp-omni)
  ├── Audio capture/playback         ├── FastAPI bridge backend      ├── MiniCPM-o 4.5 GGUF Q4_K_M
  ├── Waveform animation             ├── Routes audio ↔ Comni         ├── Port 8006 (HTTPS/WSS)
  └── Correction overlay UI         └── Port 8021                    └── 192.168.50.103
```

### Comni Inference Server (Windows, already running)
- HTTPS with self-signed certs: `https://192.168.50.103:8006`
- REST: `/health`, `/status`, `/api/presets`, `/api/assets/ref_audio`
- WebSocket (full-duplex audio): `wss://192.168.50.103:8006/ws/duplex/{session_id}`
- WebSocket (half-duplex): `wss://192.168.50.103:8006/ws/half_duplex/{session_id}`
- WebSocket (turn-based chat): `wss://192.168.50.103:8006/ws/chat`
- Self-signed SSL (must accept in clients)
- Model: MiniCPM-o 4.5 GGUF, ~10GB VRAM
- Single concurrent user per GPU (full-duplex mode)
- Session max: 600s (audio duplex), 300s (video duplex)

### Comni WebSocket Protocol (from source code analysis)
- Client connects to `wss://host:8006/ws/duplex/{session_id}`
- Server sends `{"type":"queue_done"}` when ready
- Client sends `session.init` with config (system_prompt, ref_audio, mode)
- Client streams audio: base64-encoded 16kHz mono float32 PCM
- Server responds with: `response.output.delta` (kind: listen/text/audio), transcription events
- Server audio output: 24kHz mono float32 PCM, base64-encoded
- Session closes with `session.close`

### LiveKit (Mac, to set up)
- LiveKit Server: single binary, handles WebRTC SFU
- Ports: 7880 (API), 7881 (TCP), 7882/UDP (TURN)
- Agent joins as participant, receives/publishes audio tracks

### FastAPI Bridge Backend (Mac, to build)
- Connects LiveKit Agent SDK ↔ Comni WebSocket
- Receives WebRTC audio from LiveKit → forwards to Comni
- Receives Comni audio response → publishes back to LiveKit room
- Handles session lifecycle, system prompts, voice config

### Flutter App (to build)
- LiveKit SDK for WebRTC connection
- CustomPainter for real-time waveform visualization
- Correction text overlay
- Topic/mode picker
- Session controls

## Key Files
- `~/dev/duplex-base/MiniCPM-o/` — Model source code (architecture reference)
- `~/dev/duplex-base/MiniCPM-o-Demo/` — Official demo (gateway.py, worker.py for protocol reference)
- `~/dev/duplex-base/server/` — Our FastAPI bridge backend (to build)
- `~/dev/duplex-base/app/` — Flutter app (to build)
- `~/dev/duplex-base/docs/` — Documentation

## Windows Machine (SSH accessible)
- IP: 192.168.50.103 (LAN only, no internet exposure)
- SSH: `ssh Admin@192.168.50.103` (key-based auth)
- Comni installed at: `C:\Users\Admin\AppData\Local\Comni\`
- Model at: `C:\Users\Admin\.comni\models\MiniCPM-o-4_5-gguf\`
- Gateway config: `C:\Users\Admin\AppData\Local\Comni\_internal\resources\apps\server\config.json`

## Tech Stack
- **Inference**: Comni (llama.cpp-omni) + MiniCPM-o 4.5 GGUF Q4_K_M
- **WebRTC**: LiveKit Server + LiveKit Agents SDK (Python)
- **Backend**: Python + FastAPI + websockets
- **Mobile**: Flutter + LiveKit Flutter SDK
- **Network**: LAN only (192.168.50.x), no Tailscale, no internet exposure for Windows

## Code Standards
- Python: type hints, async/await, 4-space indent
- Flutter: clean architecture, state management with Riverpod
- All WebSocket connections must handle SSL with self-signed certs
- Audio format: 16kHz mono PCM (input), 24kHz mono PCM (output from Comni)
- Base64 encode all audio over WebSocket

## Build Order
1. FastAPI bridge backend (server/) — connects LiveKit → Comni
2. Test end-to-end audio pipeline
3. Flutter app (app/) — UI + LiveKit connection
4. English tutor features (system prompts, corrections, curriculum)