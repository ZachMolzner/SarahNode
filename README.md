# SarahNode — Local-First Personal AI Assistant

SarahNode is a practical **local-first personal AI assistant** you can run on your own machine and access from computer, tablet, and phone.

It uses:
- **FastAPI** backend
- **React + Vite + TypeScript** frontend
- **WebSocket event streaming** for real-time state updates
- **OpenAI** for real LLM responses (with mock fallback)
- **ElevenLabs** for real TTS audio (with mock fallback)
- **Sarah.vrm** as the default visible assistant avatar

---

## Key Features

- Real-time assistant flow: message → moderation → LLM → optional TTS → live UI events
- Provider abstraction:
  - `LLM_PROVIDER=auto|mock|openai`
  - `TTS_PROVIDER=auto|mock|elevenlabs`
- Automatic fallback to mock providers if keys/config are missing
- VRM avatar panel with Sarah.vrm loaded from `/assets/Sarah.vrm`
- Responsive dashboard usable on desktop/tablet/phone

---

## Architecture

### Backend (`/backend`)
- FastAPI API routes:
  - `POST /api/assistant/messages`
  - `GET /api/assistant/state`
  - `GET /health`
  - `WS /ws/events`
- Stream orchestrator handles processing, state changes, and websocket event fanout.
- LLM and TTS adapters are selected at startup with robust fallback logging.

### Frontend (`/frontend`)
- React dashboard for sending messages, viewing live events, and assistant status.
- Provider status cards show real vs mock mode.
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
- `OPENAI_API_KEY` (required for real OpenAI responses)
- `OPENAI_MODEL` (default `gpt-4o-mini`)
- `ELEVENLABS_API_KEY` (required for real ElevenLabs TTS)
- `ELEVENLABS_VOICE_ID` (required for real ElevenLabs TTS)
- `ELEVENLABS_MODEL_ID` (default `eleven_multilingual_v2`)

### Frontend
- `VITE_PUBLIC_API_BASE_URL` (default `http://localhost:8000`)
- `VITE_PUBLIC_WS_BASE_URL` (default `ws://localhost:8000`)

---

## Avatar Asset Location

`Sarah.vrm` is now expected at:

`frontend/public/assets/Sarah.vrm`

The frontend loads it from:

`/assets/Sarah.vrm`

If the avatar fails to load, the UI shows an “avatar unavailable” fallback panel and continues operating.

---

## Current Limitations

- Conversation memory is currently in-memory only (no long-term persistence yet).
- TTS uses base64 audio event payloads for immediate playback; no file storage pipeline yet.
- Avatar animation is lightweight (idle/talking/blink), not a full motion rig.
