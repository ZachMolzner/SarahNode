# SarahNode — Local-First Personal Assistant

SarahNode is a LAN-accessible personal assistant control center for your own devices (desktop, tablet, phone).

## Product direction

- ✅ Not a Twitch bot
- ✅ Not a VTuber dashboard product
- ✅ Local-first personal assistant app
- ✅ FastAPI backend + React/Vite/TypeScript frontend
- ✅ Real-time event stream via WebSocket
- ✅ Optional placeholder presence/avatar layer

## Current capabilities

### Implemented

- Assistant message intake API with queueing (`/api/assistant/messages`)
- Assistant state API (`/api/assistant/state`)
- Event stream (`/ws/events`) with moderation, reply, voice, and presence events
- Provider abstraction with env-based selection (`auto`, `mock`, `openai` / `elevenlabs`)
- Safe mock fallback for LLM and TTS when provider credentials are unavailable
- Responsive web dashboard with conversation, status cards, optional presence panel, and live event log

### Placeholder

- Presence/avatar is intentionally placeholder-only right now
- Voice synthesis can run in mock mode unless ElevenLabs is configured

### Planned

- Rich local memory and task/tool integrations
- Optional production-grade avatar integrations
- Better mobile-first conversation UX and settings pages

## Architecture (current)

```text
Web UI (desktop/tablet/phone)
  -> REST /api/assistant/messages
  -> StreamOrchestrator queue
  -> Moderation + ResponsePolicy
  -> DialogueEngine (LLM adapter)
  -> TTS adapter
  -> Presence/avatar placeholder events
  -> WebSocket /ws/events
```

## Backend environment variables

```bash
APP_NAME=SarahNode Personal Assistant
ENV=dev
LOG_LEVEL=INFO

ASSISTANT_COOLDOWN_SECONDS=1.0
ASSISTANT_MAX_QUEUE_SIZE=200
ASSISTANT_MEMORY_WINDOW=25

LLM_PROVIDER=auto        # auto | mock | openai
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

TTS_PROVIDER=auto        # auto | mock | elevenlabs
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
ELEVENLABS_MODEL_ID=eleven_multilingual_v2

BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
PUBLIC_API_BASE_URL=http://localhost:8000
PUBLIC_WS_BASE_URL=ws://localhost:8000
```

## Frontend environment variables

```bash
VITE_PUBLIC_API_BASE_URL=http://<LAN_IP>:8000
VITE_PUBLIC_WS_BASE_URL=ws://<LAN_IP>:8000
```

## Local setup (LAN-ready)

### 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### 3) Open from your devices

- Desktop/tablet/phone on the same network:
  - `http://<LAN_IP>:5173`

## API quick reference

- `POST /api/assistant/messages` — enqueue a user message for assistant processing
- `GET /api/assistant/state` — read latest assistant state and memory summary
- `GET /health` — health info
- `WS /ws/events` — live stream of assistant events

Legacy compatibility endpoints still exist (`/api/chat/send`, `/api/state`) but are deprecated and should be replaced by assistant routes.
