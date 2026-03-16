# SarahNode — Modular AI VTuber Assistant (Original Character)

This project scaffolds an **original** real-time AI VTuber assistant with safety-first defaults.
It does **not** copy proprietary code, branding, voice, likeness, or personality from existing creators.

## A) Proposed architecture

The system is event-driven and decoupled with queues:

```text
Chat Source (mock/live)
   -> Chat Ingestion
   -> Priority Queue
   -> Moderation Layer
   -> Dialogue Engine (LLM adapter + persona config)
   -> Response Policy
   -> TTS Adapter
   -> Avatar Event Dispatcher
   -> WebSocket Event Bus
   -> React Dashboard

Memory Manager runs alongside orchestration:
- short-term rolling memory
- session notes
- long-term memory interface (placeholder for future provider)
```

### Module summary

- **chat ingestion**: receives raw chat messages and normalizes schema.
- **dialogue engine**: generates in-character replies via LLM abstraction.
- **memory manager**: rolling memory + session context summarization.
- **safety/moderation**: filters unsafe input categories (abuse, sexual, self-harm, illegal, prompt injection, doxxing).
- **response policy**: sanitize/refuse/redirect unsafe outputs.
- **tts wrapper**: pluggable provider interface (mock provider included).
- **avatar dispatcher**: sends avatar state events (`talking_start`, `talking_stop`, emotion events).
- **stream orchestrator**: queue control, cooldowns, speaking lock, and interrupt-safe sequencing.
- **dashboard**: real-time event/log monitoring.

---

## B) Generated folder tree

```text
backend/
  app/
    main.py
    config/
      persona.json
      settings.py
    routers/
      control.py
      health.py
    services/
      chat_ingestion.py
      dialogue_engine.py
    models/
    schemas/
      chat.py
      events.py
    core/
      container.py
      logging.py
    adapters/
      llm/
        base.py
        mock.py
      tts/
        base.py
        mock.py
      avatar/
        base.py
        mock.py
    safety/
      moderation.py
      response_policy.py
    memory/
      state_manager.py
    orchestration/
      stream_orchestrator.py
    tests/
      test_moderation.py
  requirements.txt
  .env.example

frontend/
  index.html
  package.json
  tsconfig.json
  vite.config.ts
  src/
    components/
      EventLog.tsx
      StatusCards.tsx
    pages/
      DashboardPage.tsx
    hooks/
      useEvents.ts
    lib/
      api.ts
    types/
      events.ts
    main.tsx
```

---

## C) Backend scaffold details

### Core behavior in MVP

- Accept mock chat input via API.
- Queue messages by priority.
- Moderate each message.
- Generate response from mock LLM provider using persona config.
- Apply response policy.
- Synthesize mock TTS output.
- Emit avatar/speaking events.
- Stream all events to dashboard via WebSocket.

### Safety defaults included

- Moderation categories: hate/abuse, explicit sexual content, self-harm, illegal requests, prompt injection, doxxing.
- Unsafe content gets refusal-safe fallback text.
- Cooldowns + speech lock to prevent overlapping speech/race conditions.

---

## D) React dashboard scaffold details

The dashboard shows:

- incoming events
- moderation decisions
- chosen reply
- speaking status
- active emotion

It subscribes to backend events from `ws://localhost:8000/ws/events`.

---

## Persona configuration

Edit `backend/app/config/persona.json` to change identity/tone/style without code changes.

---

## Local setup and run

## 1) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Open dashboard at:

- `http://localhost:5173`

## 3) Send mock chat message

```bash
curl -X POST "http://localhost:8000/api/mock-chat/simple?username=alex&content=hello%20nova!&priority=2"
```

---

## Development roadmap (phases)

1. **Phase 1 (MVP done by scaffold)**: queue + moderation + mock LLM/TTS/avatar + dashboard.
2. **Phase 2**: real streaming chat ingestion adapter (YouTube/Twitch/etc. where permitted).
3. **Phase 3**: production LLM + stronger prompt/policy/evals.
4. **Phase 4**: real TTS and avatar runtime with viseme timing.
5. **Phase 5**: long-term memory provider + tools/game-control modules with strict permissions.
6. **Phase 6**: observability hardening, load testing, and deployment.

---

## Next implementation steps

I can now help you implement each module step-by-step in this order:

1. Real chat ingestion adapter
2. LLM provider integration abstraction
3. TTS provider integration
4. Avatar websocket/OSC dispatcher
5. Interrupt handling + barge-in logic
6. Memory retrieval and summarization upgrades
7. Advanced moderation + policy configuration
