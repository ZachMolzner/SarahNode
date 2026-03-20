# SarahNode

SarahNode is a local-first AI companion built as a full-stack desktop/web system: a FastAPI orchestration backend, a React + TypeScript realtime client, and a Tauri shell for desktop runtime and tray-native behavior.

This project is positioned as an engineering portfolio piece focused on practical system design decisions: provider abstraction, realtime event orchestration, identity-aware dialogue context, and frontend presence behavior that reacts to assistant state instead of scripted animation loops.

---

## 1) Project overview

SarahNode provides a conversational assistant experience that combines:

- **Text + voice interaction** (message input and push-to-talk transcription).
- **Realtime state streaming** from backend to frontend over WebSocket events.
- **Avatar-driven companion UI** with deterministic presence and gesture layers.
- **Optional web-grounded answers** that can surface concise findings and sources.
- **Desktop-first runtime model** through Tauri (tray menu, summon hotkey, close-to-tray, overlay mode, sidecar backend process).

The architecture is intentionally modular so core assistant behavior can run with mock providers locally, then upgrade to live providers (OpenAI/ElevenLabs/search) via configuration.

---

## 2) Why SarahNode is different

SarahNode is not just “chat UI + LLM API.” It emphasizes **runtime orchestration and behavior systems**:

- **Provider decoupling by adapter contract** for LLM, STT, TTS, avatar, and web search so runtime capability can degrade gracefully instead of failing hard.
- **Event-first orchestration** where backend state changes (moderation, routing, reply selection, speaking state, web grounding) are emitted as explicit events that power UI behavior.
- **Identity-aware addressing** in the dialogue path (speaker resolution, addressing mode/tone directive, persisted context).
- **Deterministic presence layer** in the frontend (engagement-aware stage movement, search presentation pose, overlay-aware positioning) rather than purely random idle motion.
- **Desktop operations details** (system tray lifecycle, always-on-top/overlay toggles, summon shortcut, backend sidecar startup/teardown).

---

## 3) Core features

- Priority message queue with cooldown-aware processing.
- Safety/moderation gate before response generation.
- Capability routing (`ask_general`, `lookup_information`, `browse_web`, `coding_help`, `shutdown_command`, `smalltalk_or_greeting`).
- Optional web lookup flow with fetch/extract/synthesis and source metadata retention.
- TTS speaking synchronization events and frontend playback coordination.
- Push-to-talk transcription endpoint integrated into the same assistant pipeline.
- Web-grounded answer textbox with staged reveal and collapsible source list.
- Overlay/immersive presence modes with desktop-ground movement behavior.
- Persistent desktop settings (`always_on_top`, `overlay_mode`, `close_to_tray_on_close`, `voice_output_enabled`).

---

## 4) Architecture overview

```text
┌──────────────────────────────────────────┐
│                Frontend                  │
│ React + Vite + TypeScript + Three/VRM   │
│ - OverlayCompanionPage                   │
│ - Presence + gesture + search presentation│
└───────────────┬──────────────────────────┘
                │ REST + WebSocket
                ▼
┌──────────────────────────────────────────┐
│            FastAPI Backend               │
│ - Routers (/messages, /transcribe, /ws) │
│ - StreamOrchestrator worker + fanout     │
│ - DialogueEngine + moderation + policy   │
│ - MemoryManager + IdentityService        │
└───────┬──────────────┬───────────────┬───┘
        │              │               │
        ▼              ▼               ▼
   LLM Adapter     STT/TTS Adapters   Web Search + Page Fetch/Extract
 (mock/openai)   (openai/elevenlabs) (none/brave/serpapi optional)

Desktop runtime (optional but primary target):
Tauri shell manages window/tray/shortcut/settings and starts backend sidecar.
```

---

## 5) Frontend behavior / presence system

Frontend behavior is built from layered controllers rather than one monolithic animation module:

- **Avatar state layer** (`useAvatarState`) reacts to streamed assistant events.
- **Presence mode derivation** maps interaction context into semantic modes (speaking, presenting search results, listening, shutdown, idle transitions).
- **Presence controller stack** (zones, movement, overlay constraints, idle behavior) handles where Sarah should stand and how she settles.
- **Gesture/performance layer** adds deterministic expressive moments (startup greeting, listening acknowledgment, thinking/speaking posture, shutdown performance).
- **Expression resolver** fuses timing signals (recent interaction, search activity, interruptions/errors) into mood/expression outputs.

This split keeps behavior understandable and testable: state comes from backend events, while movement/presentation is handled by dedicated frontend systems.

---

## 6) Search presentation / reporting flow

SarahNode treats web-grounded responses as a separate presentation path:

1. Backend classifies request capability and browsing policy.
2. If enabled and needed, search provider returns ranked results.
3. Top pages are fetched + text-extracted with bounded limits/timeouts.
4. Dialogue synthesis uses extracted context and returns reply.
5. Backend emits `web_grounded_answer` event containing title, concise bullets, sources, and provider metadata.
6. Frontend normalizes payload, suppresses stale/duplicate updates, and mounts `WebAnswerTextbox`.
7. Textbox reveals in stages (heading → findings → settled), and source visibility can be expanded/collapsed.

This creates a readable “search report” UI surface without blocking the core conversational reply path.

---

## 7) Tech stack

**Backend**
- Python
- FastAPI + Uvicorn
- Pydantic / pydantic-settings
- Adapter-based integrations for OpenAI, ElevenLabs, Brave Search, SerpAPI

**Frontend**
- React 18
- TypeScript
- Vite
- Three.js + `@pixiv/three-vrm`

**Desktop shell**
- Tauri 2 (Rust)
- Tray menu + global shortcut plugin

---

## 8) Local development setup

> SarahNode can run as web app (frontend + backend dev servers) or as Tauri desktop app that launches the frontend and manages desktop behavior.

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm
- (Optional) Rust toolchain for Tauri development

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_server.py
```

Backend defaults:
- host: `0.0.0.0`
- port: `8000`
- env file support via `backend/.env` (optional)

### Frontend (Vite)

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

### Desktop shell (Tauri)

```bash
cd frontend
npm install
npm run tauri:dev
```

### Optional provider configuration

Set environment variables (typically in `backend/.env`) as needed:

- `LLM_PROVIDER` (`auto|mock|openai`)
- `STT_PROVIDER` (`auto|openai`)
- `TTS_PROVIDER` (`auto|mock|elevenlabs`)
- `OPENAI_API_KEY`
- `ELEVENLABS_API_KEY`
- `WEB_SEARCH_PROVIDER` (`none|brave|serpapi`)
- `BRAVE_SEARCH_API_KEY` / `SERPAPI_API_KEY`

---

## 9) Current limitations

- Web browsing is **opt-in** and disabled by default (`WEB_SEARCH_PROVIDER=none`), so live verification requires explicit configuration.
- `web_grounded_answer` bullets are currently derived from search snippets/context and are intentionally concise (not a full citation engine).
- Display mode defaults differ across layers (desktop settings are overlay-first; parser defaults are immersive unless overridden).
- Tauri release packaging expects a sidecar backend executable path and still needs end-to-end packaging validation in production distribution.
- Main page structure still carries dashboard-era naming in some areas despite companion-first runtime behavior.

---

## 10) Roadmap / next steps

Near-term engineering priorities:

1. **Production packaging hardening**
   - Validate sidecar build/distribution path and installer workflow.
2. **Search grounding quality**
   - Improve source ranking, attribution detail, and finding distillation quality.
3. **Presence system observability**
   - Add diagnostics/telemetry hooks for mode transitions and movement decisions.
4. **Frontend modularity pass**
   - Continue decomposing page-level orchestration into focused feature slices.
5. **Expanded automated tests**
   - Add higher-level integration coverage across event stream, search path, and desktop setting lifecycles.

---

## Repository structure (quick map)

```text
/backend
  /app
    /adapters      # provider contracts + implementations
    /services      # dialogue, search, fetch/extract, voice, policy
    /orchestration # stream orchestrator
    /routers        # API and WebSocket routes
    /memory         # state manager + persistence glue
/frontend
  /src             # React UI, behavior hooks, avatar/presence logic
  /src-tauri       # desktop shell (Rust/Tauri)
/docs              # audits, roadmap notes, and smoke checklist
```

If you’re reviewing SarahNode as a portfolio project, start with:

- `backend/app/orchestration/stream_orchestrator.py`
- `backend/app/services/dialogue_engine.py`
- `frontend/src/pages/OverlayCompanionPage.tsx`
- `frontend/src/components/WebAnswerTextbox.tsx`
- `frontend/src-tauri/src/lib.rs`
