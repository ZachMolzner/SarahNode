# SarahNode — Local-First Personal AI Assistant

SarahNode is now a local-first personal assistant app with:
- FastAPI backend
- React + Vite + TypeScript frontend
- OpenAI text generation adapter
- ElevenLabs TTS adapter
- WebSocket event bus for real-time UI updates
- Placeholder avatar bridge for future 3D/Live2D integration

## Architecture

```text
Dashboard (desktop/tablet/phone)
  -> REST /api/chat/send
  -> StreamOrchestrator queue
  -> Moderation
  -> Memory summary
  -> DialogueEngine (OpenAI adapter)
  -> ResponsePolicy
  -> TTS (ElevenLabs adapter)
  -> Avatar placeholder events
  -> WebSocket /ws/events
```

## Backend layout

- `config/settings.py`
- `adapters/llm/base.py`
- `adapters/llm/openai_client.py`
- `adapters/tts/base.py`
- `adapters/tts/elevenlabs_client.py`
- `adapters/avatar/base.py`
- `adapters/avatar/placeholder.py`
- `services/dialogue_engine.py`
- `services/chat_ingestion.py`
- `memory/state_manager.py`
- `safety/moderation.py`
- `safety/response_policy.py`
- `orchestration/stream_orchestrator.py`
- `routers/health.py`
- `routers/control.py`
- `main.py`

## Environment variables

```bash
APP_NAME=SarahNode Personal Assistant
ENV=dev
LOG_LEVEL=INFO
ASSISTANT_COOLDOWN_SECONDS=1.0
ASSISTANT_MAX_QUEUE_SIZE=200
ASSISTANT_MEMORY_WINDOW=25

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
ELEVENLABS_MODEL_ID=eleven_multilingual_v2

BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
PUBLIC_API_BASE_URL=http://localhost:8000
PUBLIC_WS_BASE_URL=ws://localhost:8000
```

For frontend, set:

```bash
VITE_PUBLIC_API_BASE_URL=http://<LAN_IP>:8000
VITE_PUBLIC_WS_BASE_URL=ws://<LAN_IP>:8000
```

## Run

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Then open `http://<LAN_IP>:5173` from desktop/tablet/phone on the same network.
