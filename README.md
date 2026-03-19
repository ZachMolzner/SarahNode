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
- VRM avatar panel with Sarah.vrm loaded from `/assets/Sarah.vrm`.
- Responsive dashboard usable on desktop/tablet/phone.

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
- React dashboard for text + voice input, live events, and assistant status.
- Push-to-talk microphone capture via `getUserMedia` + `MediaRecorder`.
- Transcript is auto-submitted through the existing assistant text message path.
- Avatar panel renders `Sarah.vrm` via Three.js + `@pixiv/three-vrm`.
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

If mic permission is denied or transcription fails, typed chat remains fully usable.

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
- Avatar animation is lightweight (idle/listening/thinking/talking), not a full motion rig.
