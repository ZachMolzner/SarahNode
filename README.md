# SarahNode — Local-First Personal AI Assistant

SarahNode is a practical **local-first personal AI assistant** you can run on your own machine and access from computer, tablet, and phone.

It uses:
- **FastAPI** backend
- **React + Vite + TypeScript** frontend
- **WebSocket event streaming** for real-time state updates
- **OpenAI** for real LLM responses and speech-to-text (with fallback-safe behavior)
- **ElevenLabs** for real TTS audio (with mock fallback)
- **Sarah.vrm** as the default visible assistant avatar

---

## Key Features

- Real-time assistant flow: message → moderation → LLM → optional TTS → live UI events.
- Voice push-to-talk flow: mic record → `/api/assistant/transcribe` → transcript → existing assistant message pipeline.
- Provider abstraction:
  - `LLM_PROVIDER=auto|mock|openai`
  - `TTS_PROVIDER=auto|mock|elevenlabs`
  - `STT_PROVIDER=auto|openai`
- Automatic fallback behavior and clear errors when required credentials are missing.
- Immersive avatar-first launch mode where Sarah is the dominant fullscreen presence.
- Cinematic stage presentation with layered gradients, spotlight glow, and subtle depth/vignette treatment to keep Sarah as the focal point.
- Presence behavior system: Sarah now uses deterministic contextual stage behavior (not random motion) to choose where to stand, when to approach, and when to settle.
- Reactive gesture/performance system layered above movement + presence for intentional startup greeting, listening acknowledgments, thinking posture, response-delivery emphasis, and calm reset behavior.
- Stage zones and contextual occupancy: center presentation, relaxed side anchors, listening anchor, caption-friendly zone, and shutdown settle zone.
- Engagement-based positioning: interaction heat rises during voice/transcript/reply activity and softly decays during idle to guide approach/retreat behavior.
- Attention and focus behavior: Sarah blends viewer focus, neutral idle gaze, thinking/inward focus, and subtle caption/overlay-aware focus shifts.
- Idle micro-behaviors: gentle low-amplitude shifts and posture/gaze adjustments when calm, with suppression during listening/thinking/shutdown.
- Overlay awareness: menu/transcript/caption/shutdown overlays softly bias zone selection to reduce visual conflict without mechanical snapping.
- Subtitle-style on-stage captions for user transcripts and Sarah replies (lightweight, auto-fading, and separate from transcript history).
- Centralized voice orchestration layer that is ElevenLabs-first with graceful browser speech fallback.
- Startup greeting, assistant replies, and shutdown goodbye now all route through one shared voice orchestration API.
- Sarah voice profile tuning is centralized (`frontend/src/lib/voiceProfile.ts`) for tone + ElevenLabs + browser fallback behavior.
- Startup and shutdown use curated line pools with anti-repeat selection (`frontend/src/lib/voiceLines.ts`).
- Startup includes a one-time happy/excited Sarah greeting with caption sync and provider fallback handling.
- Shutdown includes a dedicated goodbye line plus a respectful Japanese-bow-inspired performance before close/fallback handling.
- Minimal overlays for mic/listening, connection status, optional transcript, and tucked-away controls.
- Voice shutdown intent handling with confirmation and graceful browser-safe fallback.
- VRM avatar panel with Sarah.vrm loaded from `/assets/Sarah.vrm`.
- Responsive experience across desktop/tablet/phone.

---

## Architecture

### Backend (`/backend`)
- FastAPI API routes:
  - `POST /api/assistant/messages`
  - `POST /api/assistant/transcribe`
  - `POST /api/assistant/voice/event`
  - `GET /api/assistant/state`
  - `GET /health`
  - `WS /ws/events`
- Stream orchestrator handles processing, state changes, and websocket event fanout.
- LLM, TTS, and STT adapters are selected at startup with robust fallback logging.

### Frontend (`/frontend`)
- Immersive React stage with Sarah centered by default and controls behind compact overlays/drawers.
- Push-to-talk microphone capture via `getUserMedia` + `MediaRecorder`.
- Transcript is auto-submitted through the existing assistant text message path.
- Avatar panel renders `Sarah.vrm` via Three.js + `@pixiv/three-vrm` with smooth mood/state transitions.
- Presence layer is implemented above raw movement interpolation (`presenceController` + `stageZones` + `usePresenceBehavior`) and feeds zone, target, engagement, and focus outputs into the existing movement/VRM pipeline.
- Gesture/performance layer is implemented above presence and locomotion (`gestureController` + `useGesturePerformance`) and contributes deterministic expressive offsets, priorities, cooldowns, and recovery easing.
- Speaking sync improvements: talking motion now follows TTS playback timing when available, with text-duration fallback when no audio payload exists.
- Voice orchestration module (`voiceOrchestrator`) provides `speakText`, `stopSpeaking`, and status/debug metadata across ElevenLabs and browser fallback paths.
- Browser-safe stage/screen abstraction (`ScreenEnvironment` + stage bounds provider) for future native monitor-aware movement in Tauri/Electron.
- Auto-play + replay support for generated speech audio.

---

## Setup

## 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Run backend:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 2) Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev -- --host 0.0.0.0 --port 5173
```

---

## Required Environment Variables

### Backend
- `LLM_PROVIDER` = `auto` | `mock` | `openai`
- `TTS_PROVIDER` = `auto` | `mock` | `elevenlabs`
- `STT_PROVIDER` = `auto` | `openai`
- `OPENAI_API_KEY` (required for real OpenAI responses/transcription)
- `OPENAI_MODEL` (default `gpt-4o-mini`)
- `OPENAI_TRANSCRIPTION_MODEL` (default `whisper-1`)
- `ELEVENLABS_API_KEY` (required for real ElevenLabs TTS)
- `ELEVENLABS_VOICE_ID` (required for real ElevenLabs TTS)
- `ELEVENLABS_MODEL_ID` (default `eleven_multilingual_v2`)

### Frontend
- `VITE_PUBLIC_API_BASE_URL` (default `http://localhost:8000`)
- `VITE_PUBLIC_WS_BASE_URL` (default `ws://localhost:8000`)

---

## Voice Testing Quick Start

1. Start backend and frontend.
2. Open dashboard in your browser.
3. Click **Start Recording** and allow microphone permission.
4. Speak, then click **Stop Recording**.
5. Confirm UI shows transcribing, transcript appears in message box, and message is sent.
6. Confirm assistant response appears and (if TTS enabled) audio plays.
7. Confirm startup line and shutdown goodbye are selected from small anti-repeat pools.
8. If ElevenLabs is unavailable, confirm browser speech fallback still speaks with captions intact.

If mic permission is denied or transcription fails, typed chat remains fully usable.

## Voice Profile Tuning

Tune Sarah's voice behavior in:

- `frontend/src/lib/voiceProfile.ts`
  - ElevenLabs defaults:
    - `stability: 0.46`
    - `similarity_boost: 0.76`
    - `style: 0.18`
    - `use_speaker_boost: false`
  - Browser fallback defaults:
    - `rate: 0.92`
    - `pitch: 1.3`
    - `volume: 1.0`

Startup/listening/shutdown line pools and anti-repeat behavior live in:

- `frontend/src/lib/voiceLines.ts`

---

## Avatar Asset Location

`Sarah.vrm` is expected at:

`frontend/public/assets/Sarah.vrm`

The frontend loads it from:

`/assets/Sarah.vrm`

---

## Current Limitations

- Stage 1 push-to-talk is implemented; always-listening/VAD is a future extension.
- Conversation memory is currently in-memory only (no long-term persistence yet).
- TTS uses base64 audio event payloads for immediate playback; no file storage pipeline yet.
- Browser builds support movement within the current viewport/stage only; true cross-monitor geometry requires a native wrapper (Tauri/Electron) that can provide monitor bounds and window placement APIs.
- Multi-display movement architecture is prepared through `ScreenEnvironment` and stage-bounds abstractions, but browser runtime currently uses viewport-safe regions.
- Avatar animation remains lightweight and stable (no full mocap rig / phoneme viseme pipeline yet).


## Stage Presence and Display-Space Notes

What works now in browser:
- Sarah can move smoothly across the visible stage area with intentional behavior priorities (shutdown > listening > talking > thinking > overlay-aware reposition > idle relaxed presence).
- Stage zones are computed from normalized stage coordinates and adapt to viewport bounds, preserving browser-safe behavior while remaining ready for native display-region inputs.
- Presence behaviors include anti-pacing safeguards (zone dwell time, movement cooldowns, target hysteresis, and movement suppression during high-priority states).
- Stage movement uses normalized stage coordinates and interpolation to avoid jitter, with graceful pseudo-walking body rhythm when no dedicated walk animation exists.
- The browser implementation uses current viewport/stage bounds and can optionally read segmented window regions where supported.

What needs a native wrapper for full monitor-aware behavior:
- Enumerating full multi-monitor geometry reliably (all displays, work areas, DPI-scaled coordinates).
- True cross-monitor routing and window-aware movement beyond the current browser viewport.
- OS-level placement constraints and display targeting logic for persistent avatar movement across monitors.

Planned extension path:
1. Keep movement logic display-agnostic via `ScreenEnvironment` / `StageBoundsProvider`.
2. Keep presence behavior display-agnostic via normalized stage zones + overlay/layout inputs.
3. Add a Tauri/Electron monitor provider that supplies monitor regions and active-window coordinates.
4. Feed those regions into the same movement + presence controllers without rewriting avatar behavior logic.


## Shutdown Behavior

SarahNode supports voice-triggered shutdown intents (for example: "Sarah, close program" or "close SarahNode").

- Most shutdown phrases require confirmation (e.g., "yes" / "confirm") before ending the session.
- On confirmed shutdown, Sarah performs a dedicated goodbye sequence: a spoken/captioned goodbye line plus a respectful Japanese-bow-inspired animation, then active listening/audio are halted and close is requested.
- Browser tabs may block programmatic close calls; when that happens SarahNode falls back to: **"Session closed. You can now close this tab."**
- The close behavior is isolated behind a shell abstraction so Tauri/Electron window-close APIs can be added later without changing intent parsing logic.
