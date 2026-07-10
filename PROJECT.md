# Full-Duplex Voice AI Platform — Project Documentation

> **Last updated:** 2026-07-08  
> **Status:** Inception / Setup Phase  
> **Owner:** Pooh (Weike Liao)  

---

## 1. Project Overview

### Goal
Build a **full-duplex conversation LLM platform** — a real-time voice AI that can listen and speak simultaneously, with native audio understanding (accent, emotion, pronunciation) from raw waveforms. The primary application is an **English tutor**, but the platform is designed to be general-purpose.

### Key Differentiator
Unlike cascade pipelines (STT → LLM → TTS), this platform uses a **native speech-to-speech model** that processes raw audio tokens directly — preserving paralinguistic information (accent, emotion, prosody) that text-based pipelines lose.

### Design Philosophy
- **No shortcuts** — aim for a great/perfect product, no deadline (hobby project)
- **Optimal tech stack** — every component chosen for performance, not convenience
- **Lean Windows system** — only inference server runs on Windows, no Docker, no dev tools
- **LAN only** — no internet exposure, no Tailscale needed

---

## 2. Model Selection

### Decision: MiniCPM-o 4.5 (openbmb/MiniCPM-o-4_5)

**Why not Qwen3-Omni-30B-A3B:**
- Qwen3-Omni-30B is turn-based only (not full-duplex) — the "native turn-taking" claim is an architectural capability not exposed through any serving API
- Qwen3-Omni-Flash (Dec 2025) exists but is **API-only** (DashScope), not open-weight on HuggingFace
- 30B MoE barely fits RTX 3090 at int4 (20.3GB), OOM at bf16

**Why MiniCPM-o 4.5 wins:**
| Dimension | MiniCPM-o 4.5 | Qwen3-Omni-30B |
|---|---|---|
| Full-duplex | ✅ Native TDM | ❌ Turn-based |
| VRAM bf16 | 19GB ✅ | OOM ❌ |
| VRAM int4 | 11GB ✅ | 20GB ⚠️ |
| Inference speed | 212 tok/s (int4) | 148 tok/s (int4) |
| Benchmarks | Higher (OpenCompass 77.6) | Lower (75.7) |
| LiveKit demo | ✅ Official | ❌ Nothing |
| Voice cloning | ✅ From reference clip | Limited |
| llama.cpp | ✅ Full C++ omni | ❌ |
| Proactive interaction | ✅ 1Hz decision | ❌ |

### Model Architecture (MiniCPM-o 4.5)
- **Total params:** 9B (dense)
- **Components:** SigLip2 (vision) + Whisper-medium (audio) + CosyVoice2 (speech TTS) + Qwen3-8B (LLM backbone)
- **Architecture:** End-to-end omni-modal, all encoders/decoders densely connected to LLM via hidden states
- **Full-duplex mechanism:** Omni-Flow with TDM (Time-Division Multiplexing)
  - Per-second unit loop: `streaming_prefill()` → `streaming_generate()`
  - Special tokens: `<unit>`, `<|listen|>`, `<|speak|>`, `<|tts_bos|>`, `<|tts_eos|>`, `<|turn_eos|>`
  - Model autonomously decides each second whether to listen or speak
- **Proactive interaction:** LLM monitors input at 1Hz, can initiate speech unprompted
- **Voice cloning:** Audio system prompt with reference clip, 3 presets + custom

### Team Behind the Model
- **OpenBMB** = THUNLP (Tsinghua University NLP Lab) + ModelBest (commercial startup)
- Led by Prof. Zhiyuan Liu and Prof. Maosong Sun
- GitHub: 6.8K followers, 80 repos (ChatDev 33.7K stars, VoxCPM 32.8K stars, MiniCPM-V 25.8K stars)
- License: Apache 2.0

### Known Limitations
1. **Mixed English/Chinese output** in omni mode — fix with strong system prompt
2. **Speech mispronunciation** in full-duplex omni mode — CosyVoice2 garbles under TDM contention
3. **Single user per GPU** in full-duplex (KV cache occupied for entire session)
4. **600-second session limit** in demo — need session reconnection for long conversations
5. **1Hz decision frequency** — ~1-1.5s total round-trip latency (upper end of acceptable)

### Operating Modes
| Mode | Speech Quality | Interruption | Best for |
|---|---|---|---|
| Full-duplex | ⚠️ Can mispronounce | ✅ Yes | Natural conversation |
| Half-duplex | ✅ Clean | ❌ No | Teaching (clear audio) |
| Turn-based | ✅ Best | ❌ No | Structured lessons |

---

## 3. Architecture

```
Mac (development)                         Windows RTX 3090 (inference only)
┌──────────────────────────┐              ┌──────────────────────────────┐
│ VS Code / IDE            │              │ Comni (llama.cpp-omni)        │
│ LiveKit Server (binary)  │── LAN SSH ──▶│ GGUF model (~5GB Q4_K_M)     │
│ FastAPI backend          │  192.168.    │ Port: :9060 (or similar)      │
│ Flutter app (dev)        │  50.103      │ ~10GB VRAM used               │
│ Git, build tools         │              │ No IDE, no Docker, no dev     │
│ ~/dev/duplex-base/       │              │ tools — just inference        │
└──────────────────────────┘              └──────────────────────────────┘
```

### Component Breakdown

**Windows (Inference Server):**
- `Comni` (llama.cpp-omni) — pre-built C++ binary, runs MiniCPM-o 4.5 GGUF
- GGUF model file: `MiniCPM-o-4_5-Q4_K_M.gguf` (~4.8GB)
- Reference audio files for voice presets
- Python (only for FastAPI bridge if needed)
- OpenSSH Server (for remote management from Mac)

**Mac (Development + Serving):**
- LiveKit Server — WebRTC SFU (single binary, CPU-only)
- FastAPI backend — bridges LiveKit audio frames to Windows inference endpoint
- Flutter app — mobile UI with LiveKit SDK
- All development tools, git repos, testing

### What's Pre-built (from MiniCPM-o-Demo repo)
1. **LiveKit WebRTC demo** — `OpenSQZ/MiniCPM-V-CookBook/demo/web_demo/WebRTC_Demo/`
   - LiveKit Server v1.5.3 + FastAPI backend + Vue frontend
   - One-click deployment script
   - Docker compose (we won't use Docker on Windows)
   - Explicitly tested on RTX 3090 ("Comfortable" for duplex mode)
   - Windows deployment script (`deploy_all_win.ps1`)
2. **PyTorch demo** — `OpenBMB/MiniCPM-o-Demo` (260 stars)
   - WebSocket-based realtime API
   - 4 modes: turn-based, half-duplex, omni full-duplex, audio full-duplex
   - Mobile-responsive React frontend
3. **llama.cpp-omni** — `tc-mb/llama.cpp-omni` (188 stars)
   - Full C++ implementation with omni streaming
   - Pre-built Windows installer: `Comni-Setup-1.0.22-win64.exe` (538MB)
   - Auto-downloads model on first launch

### What We Need to Build
1. Flutter app UI (waveform animation, correction display, topic picker)
2. English tutor system prompt (correction logic, curriculum)
3. Adapt existing LiveKit demo backend for our specific use case
4. Session management (reconnection, context preservation)

---

## 4. Hardware & Environment

### Windows Machine (Pooh-Desktop)
- **IP:** 192.168.50.103 (LAN only)
- **User:** Admin (SSH key auth configured)
- **SSH:** OpenSSH Server installed, public key auth via `C:\ProgramData\ssh\administrators_authorized_keys`
- **GPU:** RTX 3090, 24GB VRAM, ~1.8GB used by desktop apps
- **CUDA:** 13.3, Driver 610.62
- **Python:** 3.12.10 (with pip 25.0.1)
- **Git:** Installed
- **Docker:** NOT installed (by choice — lean system)
- **Tailscale:** NOT installed (LAN only, no internet exposure)

### Mac (Development Machine)
- **Path:** ~/dev/duplex-base/
- **Tools:** VS Code, terminal, git, all dev tools
- **LiveKit Server:** To be installed (single binary)
- **Flutter SDK:** To be installed

### Network
- Both machines on same LAN (192.168.50.x)
- SSH from Mac → Windows works
- No Tailscale/internet exposure needed

---

## 5. Cloned Repos

```
~/dev/duplex-base/
├── MiniCPM-o/          # Model code, architecture, docs, web demos
├── MiniCPM-o-Demo/     # Official PyTorch + WebRTC demo system (260 stars)
├── PROJECT.md          # This file
```

### Key Source Files
- `~/dev/duplex-base/MiniCPM-o-Demo/gateway.py` — Gateway (routing, queuing, WS proxy)
- `~/dev/duplex-base/MiniCPM-o-Demo/worker.py` — Worker (runtime protocol proxy)
- `~/dev/duplex-base/MiniCPM-o-Demo/runtime/session.py` — Session management
- `~/dev/duplex-base/MiniCPM-o-Demo/docker-compose.multi.yml` — Multi-worker per GPU
- `~/dev/duplex-base/MiniCPM-o/web_demos/minicpm-o_2.6/model_server.py` — Streaming model server (936 lines)

---

## 6. Research Findings (Deep Dive Notes)

### How vLLM-Omni Realtime API Works
- Exposes `/v1/realtime` WebSocket endpoint (OpenAI-compatible)
- Protocol: `session.update` → `input_audio_buffer.append` (PCM16 chunks) → `input_audio_buffer.commit` (final=True) → receive `response.audio.delta` → `response.audio.done`
- **Request-response only** — not continuous full-duplex
- No server-side VAD or turn detection in the protocol
- Client controls conversation flow (when to commit = when user stopped talking)

### How LiveKit Handles Turn Detection
- `TurnDetectionMode` = `"stt" | "vad" | "realtime_llm" | "manual" | _TurnDetector | _StreamingTurnDetector`
- **Semantic turn detector** — transformer model predicts `end_of_turn_probability` and `backchannel_probability`
- **Streaming turn detector** — processes audio frames continuously, predicts turn in real-time
- `RealtimeModel` abstraction with `turn_detection: bool` and `audio_output: bool` capabilities
- Existing plugins: OpenAI Realtime API, Ultravox (audio-in, text-out only)

### Existing Open-Source Full-Duplex Projects Found
| Project | Stars | Approach |
|---|---|---|
| **MiniCPM-o 4.5 + LiveKit demo** | — | True full-duplex via TDM, LiveKit WebRTC (our choice) |
| Vui (fluxions-ai) | 716 | Cascade (ASR → local LLM → TTS), WebRTC, OpenAI Realtime API compatible |
| X-Talk | 217 | Cascade (SenseVoice → Qwen3 → IndexTTS), full-duplex WebSocket |
| Ultravox + LiveKit | — | Native audio-in, text-out only, API-only (no self-host realtime) |

### Gap Nobody Has Filled
- No self-hosted, full-duplex, native S2S voice AI existed before MiniCPM-o 4.5
- MiniCPM-o 4.5 is the first open-weight model with true full-duplex + serving infrastructure
- The LiveKit WebRTC demo from OpenBMB is the first working integration

---

## 7. Session Reconnection Notes

- Demo system: KV cache lives in worker memory during session
- On `session.close`: worker sends `session.closed` and **clears KV cache** (`reset_half_duplex_session()`)
- **Reconnection = fresh session** in the demo (no context preserved)
- For production: keep transcript client-side, replay as system prompt on reconnect
- Model has 256K+ context window (Qwen3-8B backbone) — plenty of room for conversation history
- Raw audio context (emotion, accent) is lost on reconnect; semantic history can be preserved

---

## 8. Current Progress

### Completed
- [x] Research: Model selection (MiniCPM-o 4.5 chosen over Qwen3-Omni-30B)
- [x] Research: Architecture deep dive (TDM, full-duplex, serving options)
- [x] Research: Existing open-source projects surveyed
- [x] Research: Team/background verification (OpenBMB / THUNLP / ModelBest)
- [x] Environment: Windows SSH access configured (key auth via administrators_authorized_keys)
- [x] Environment: Windows system audit (GPU, Python, drivers verified)
- [x] Repos: MiniCPM-o and MiniCPM-o-Demo cloned to ~/dev/duplex-base/
- [x] Download: Comni installer (Comni-Setup-1.0.22-win64.exe, 538MB) downloaded to Windows
- [x] **Comni installer needs manual run** — silent install didn't work (NSIS installer needs GUI interaction)
- [x] Download MiniCPM-o 4.5 Q4_K_M GGUF model (~4.8GB) to Windows

### Pending
- [ ] Install Python backend dependencies on Windows (fastapi, uvicorn, websockets) — only if needed
- [ ] Download reference audio files for voice presets
- [ ] Start Comni inference server and verify it works
- [ ] Set up LiveKit Server on Mac
- [ ] Set up FastAPI bridge backend on Mac
- [ ] Test end-to-end: Mac backend → Windows inference → audio response
- [ ] Build Flutter app UI
- [ ] Write English tutor system prompt
- [ ] Implement session management with reconnection

---

## 9. Next Steps (Cold Pickup Instructions)

### Immediate Next Actions

3. **Start inference server** and verify GPU utilization:
   ```bash
   ssh Admin@192.168.50.103 "nvidia-smi"
   ```

4. **Install LiveKit Server on Mac**:
   ```bash
   brew install livekit
   ```

5. **Set up FastAPI bridge** — adapt the WebRTC demo backend from MiniCPM-o-Demo

### Key SSH Commands
```bash
# Test SSH connection
ssh Admin@192.168.50.103 "echo OK"

# Check GPU status
ssh Admin@192.168.50.103 "nvidia-smi"

# Check if Comni installed
ssh Admin@192.168.50.103 "where Comni 2>&1 & dir \"C:\\Program Files\\Comni\" 2>&1"

# Check disk space
ssh Admin@192.168.50.103 "wmic logicaldisk get size,freespace,caption"
```

### Important Context for Cold Pickup
- **Model:** MiniCPM-o 4.5, 9B params, GGUF Q4_K_M (~4.8GB), fits RTX 3090 at ~10GB VRAM
- **Inference:** Comni (llama.cpp-omni) pre-built binary, not Docker, not PyTorch
- **Transport:** LiveKit WebRTC (official demo exists in MiniCPM-o-Demo repo)
- **Dev split:** Mac develops everything, Windows only runs inference server
- **No Docker on Windows** — bare metal only
- **No Tailscale** — LAN only (192.168.50.x)
- **Comni installer is NSIS** — silent install failed, needs manual GUI install
- **Model auto-downloads on first Comni launch** but we want to control the path

### Questions Still Open
- Should we use half-duplex or full-duplex for MVP? (Half-duplex = cleaner speech, full-duplex = interruption support)
- How to handle session reconnection with context preservation?
- Flutter vs other mobile framework — leaning Flutter + LiveKit SDK
- Whether to adapt the existing WebRTC demo backend or write from scratch

---

## 10. Research Sources

- HuggingFace: `openbmb/MiniCPM-o-4_5` (411K downloads), `openbmb/MiniCPM-o-4_5-gguf` (19K downloads)
- GitHub: `OpenBMB/MiniCPM-o` (25.8K stars), `OpenBMB/MiniCPM-o-Demo` (260 stars)
- GitHub: `tc-mb/llama.cpp-omni` (188 stars, pre-built Comni binaries)
- GitHub: `livekit/agents` (LiveKit Agents framework, RealtimeModel abstraction)
- GitHub: `vllm-project/vllm-omni` (vLLM-Omni, /v1/realtime endpoint)
- GitHub: `fluxions-ai/vui` (716 stars, cascade voice assistant)
- GitHub: `xcc-zach/xtalk` (217 stars, full-duplex cascade)
- arXiv: `2604.27393` (MiniCPM-o technical report)
- Qwen blog: `qwen3-omni-flash-20251201` (Qwen3-Omni-Flash is API-only, not open-weight)