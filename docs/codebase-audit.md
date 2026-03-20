# SarahNode Codebase Audit (Professional Maintainability Review)

Date: 2026-03-20

Scope reviewed:
- `frontend/src` (React + TypeScript)
- `backend/app` (FastAPI + services)
- Existing project docs and top-level structure

This audit focuses on code quality, maintainability, naming, structure, and consistency for long-term professional development while preserving current behavior.

---

## Executive summary

SarahNode already has a **strong domain-driven intent** (assistant orchestration, provider adapters, identity, voice, avatar/presence), and many files are named clearly enough to infer purpose quickly. The largest maintainability risk is **concentration of too many responsibilities into a few high-churn files**, especially the main frontend page and some backend coordination modules.

If you only do one thing next: split orchestration-heavy files into smaller domain modules while preserving API behavior.

---

## Critical findings

### 1) Frontend “god page” (`OverlayCompanionPage`) owns too many responsibilities
- **Problem**: `OverlayCompanionPage.tsx` is ~1,258 lines and currently mixes UI composition, websocket event interpretation, voice orchestration, shutdown intent flow, identity/memory CRUD wiring, timing choreography, and style definitions in one file.
- **Why it matters**: This makes onboarding slower, increases regression risk, and turns small changes into high-context edits. It also makes test isolation difficult because behavior is spread across many local states/effects.
- **Recommended fix**:
  1. Keep the page as an assembly/composition layer only.
  2. Extract feature slices:
     - `useAssistantSessionController` (send/transcribe/events/status)
     - `useShutdownFlow` (intent match + confirm + close)
     - `useWebAnswerPresentation` (reveal state/timers)
     - `OverlayChrome` and `AdminSurface` presentational components
  3. Move style constants into per-component style modules (or CSS modules) to reduce file length and ownership overlap.
- **Affected files/folders**:
  - `frontend/src/pages/OverlayCompanionPage.tsx`
  - `frontend/src/components/*`
  - `frontend/src/hooks/*`

### 2) Event typing is too loose for a central event-driven architecture
- **Problem**: Frontend event payloads are mostly `Record<string, unknown>`, and event types allow fallback to arbitrary `string`, leading to repeated ad-hoc payload extraction and narrowing.
- **Why it matters**: This weakens TypeScript’s value exactly where reliability matters most (state transitions from backend events). It increases runtime-only bugs and makes refactoring risky.
- **Recommended fix**:
  1. Introduce a discriminated union keyed by `type` (e.g., `AssistantStateEvent`, `ReplySelectedEvent`, `VoiceEvent`, etc.).
  2. Add runtime guards in the websocket parsing layer and return a typed `KnownSystemEvent | UnknownSystemEvent`.
  3. Replace stringly payload access (`payload["state"]`) with strongly typed fields.
- **Affected files/folders**:
  - `frontend/src/types/events.ts`
  - `frontend/src/hooks/useEvents.ts`
  - `frontend/src/hooks/useAvatarState.ts`
  - `frontend/src/pages/OverlayCompanionPage.tsx`

### 3) Backend control router bundles multiple domains into one API module
- **Problem**: `control.py` handles assistant messages, identity profiles, memory CRUD, voice events, transcription, and state/status responses in one router file.
- **Why it matters**: Domain boundaries are blurred; future additions increase merge conflicts and make policy/validation consistency harder to enforce.
- **Recommended fix**:
  1. Split routes by domain while preserving endpoint paths:
     - `routers/assistant.py`
     - `routers/identity.py`
     - `routers/memory.py`
     - `routers/voice.py`
  2. Keep one `api_router.py` that includes each sub-router.
  3. Standardize request/response model naming per domain.
- **Affected files/folders**:
  - `backend/app/routers/control.py`
  - `backend/app/main.py`
  - `backend/app/schemas/*`

---

## Important findings

### 4) Global container singletons and mutable provider-selection globals reduce testability
- **Problem**: `container.py` constructs long-lived singletons at import time and tracks provider selection through module-level mutable globals (`llm_selection`, `tts_selection`, etc.).
- **Why it matters**: This complicates isolated testing and can cause hidden coupling/order-dependent behavior (especially as environments/tests expand).
- **Recommended fix**:
  1. Encapsulate runtime dependencies in an explicit `AppContainer` instance.
  2. Build providers lazily at startup with explicit lifecycle hooks.
  3. Move provider status to container state rather than module globals.
- **Affected files/folders**:
  - `backend/app/core/container.py`
  - `backend/app/main.py`
  - `backend/app/tests/*`

### 5) Identity service has strong functionality but mixed responsibilities and hardcoded household policy
- **Problem**: `IdentityService` handles persistence, profile CRUD, memory CRUD, speaker resolution, and addressing policy in one class, with household-specific behavior (“zach”, “aleena”, “Mama”) embedded directly.
- **Why it matters**: Good for rapid iteration, but difficult to generalize, reason about, and test by behavior slice.
- **Recommended fix**:
  1. Separate into collaborators:
     - `IdentityStore` (load/save)
     - `IdentityRegistry` (profiles/facts/memory item CRUD)
     - `AddressingPolicyEngine` (speaker/address/tone rules)
  2. Keep household-specific defaults in config/data files; keep policy engine generic.
- **Affected files/folders**:
  - `backend/app/services/identity_service.py`
  - `backend/app/schemas/identity.py`
  - `backend/app/data/identity_memory.json`

### 6) Naming consistency around “display/overlay/immersive mode” is close, but not fully unified
- **Problem**: Mode-related concepts are represented with overlapping but different naming layers (`InteractionMode`, `DisplayMode`, `preferredMode`, `overlayMode`, runtime-derived mode state).
- **Why it matters**: Semantically adjacent names with slight differences are easy to misuse, especially when desktop/browser behavior diverges.
- **Recommended fix**:
  1. Define one canonical mode vocabulary in a shared frontend domain module.
  2. Replace booleans (`overlayMode`) with canonical enum mode where possible.
  3. Keep adapter translation at boundaries (UI settings ↔ native bridge).
- **Affected files/folders**:
  - `frontend/src/types/settings.ts`
  - `frontend/src/lib/displayMode.ts`
  - `frontend/src/hooks/useSettingsStore.ts`

### 7) Inline style usage is consistent within files but creates maintainability friction at scale
- **Problem**: Major UI files hold many `CSSProperties` constants inline, including page-level and component-level styles mixed in logic files.
- **Why it matters**: Styling changes become code edits in behavior-heavy files; visual consistency and reuse become harder as UI grows.
- **Recommended fix**:
  1. Start by extracting style groups from the largest files (`OverlayCompanionPage`, `WebAnswerTextbox`, `SettingsPanel`) into adjacent style modules.
  2. Optionally migrate to CSS modules or a single utility-based approach later; do not churn all at once.
- **Affected files/folders**:
  - `frontend/src/pages/OverlayCompanionPage.tsx`
  - `frontend/src/components/WebAnswerTextbox.tsx`
  - `frontend/src/components/SettingsPanel.tsx`

### 8) Tests exist and provide value, but depth and isolation are uneven
- **Problem**: Current backend tests cover route shape and capability routing, but many assertions are broad, and stateful runtime pieces (identity persistence/container lifecycles/orchestrator behavior) are lightly covered.
- **Why it matters**: Refactors in critical orchestration code will have weaker safety rails.
- **Recommended fix**:
  1. Add focused service-level tests for `IdentityService` behavior slices and `StreamOrchestrator` transitions.
  2. Add deterministic fixtures/temp data paths for tests touching persisted identity data.
  3. Keep route tests, but add stronger schema/content assertions for core responses.
- **Affected files/folders**:
  - `backend/app/tests/*`
  - `backend/app/services/identity_service.py`
  - `backend/app/orchestration/stream_orchestrator.py`

---

## Nice-to-have findings

### 9) Timing constants/magic numbers are improving but still scattered
- **Problem**: The frontend has many hardcoded timing values across page and component orchestration.
- **Why it matters**: Animation/behavior tuning becomes tedious and less discoverable.
- **Recommended fix**: Centralize timing tokens per domain (`voice`, `presence`, `web-answer-presentation`) and consume through small config objects.
- **Affected files/folders**:
  - `frontend/src/pages/OverlayCompanionPage.tsx`
  - `frontend/src/components/WebAnswerTextbox.tsx`
  - `frontend/src/lib/*controller*.ts`

### 10) A few historical/legacy seams remain visible
- **Problem**: Legacy API alias (`/chat/send`) and docs acknowledging dashboard-centric legacy naming indicate transitional architecture.
- **Why it matters**: Transitional seams are fine, but should be deliberately tracked so they do not become permanent confusion points.
- **Recommended fix**: Keep compatibility path, but mark explicit deprecation target/date and centralize compatibility notes.
- **Affected files/folders**:
  - `backend/app/routers/control.py`
  - `docs/current-state-audit-2026-03-20.md`

---

## Strengths worth preserving

1. **Clear high-level domain decomposition** in backend (`adapters`, `services`, `orchestration`, `safety`, `schemas`) is a strong base for professional scaling.
2. **Provider abstraction + fallback model** is practical and robust for local-first runtime constraints.
3. **Frontend domain modules are intentionally named** (`presenceController`, `gestureController`, `stageController`, `voiceOrchestrator`) and communicate behavior purpose well.
4. **Type usage is generally disciplined** in many places (explicit model types, union literals, API model typing), despite event-payload weak spots.
5. **Documentation quality is above average** for a personal project; architecture and runtime intent are clearly communicated.

---

## Naming/style patterns that are already good

- Verb-oriented hook names (`useEvents`, `useAvatarState`, `useSettingsStore`) are clear and idiomatic.
- “Controller/Service/Adapter” suffixing is mostly used consistently with role intent.
- Cross-cutting vocabulary (`presence`, `gesture`, `overlay`, `identity`, `memory`, `orchestrator`) is stable and readable.
- API and schema naming is mostly explicit enough for contributors to infer behavior quickly.

---

## Recommended cleanup order (lowest risk to highest leverage)

1. **Type safety pass on event contracts** (frontend only; minimal behavior risk).
2. **Route module split in backend** (no endpoint changes, just organizational boundaries).
3. **Extract `OverlayCompanionPage` orchestration hooks/components** in small steps.
4. **Refactor `IdentityService` into policy/store collaborators** while preserving API outputs.
5. **Container lifecycle rework** to reduce globals and improve deterministic testing.

---

## Top 5 issues to fix first

1. Break up `OverlayCompanionPage` into focused controllers + presentational components.
2. Replace loose `Record<string, unknown>` event payload handling with discriminated event unions.
3. Split `backend/app/routers/control.py` by domain to restore API module boundaries.
4. Decompose `IdentityService` to separate persistence from addressing policy.
5. Replace global mutable provider-selection state in `container.py` with instance-managed state.

---

## What should **not** be refactored right now (already strong)

- Backend top-level layering (`adapters/services/orchestration/schemas/safety`) should be preserved.
- Provider fallback strategy and local-first runtime behavior should be preserved.
- Frontend domain vocabulary around avatar/presence/gesture should be preserved; refine boundaries without renaming everything.
- Existing docs structure should be preserved and extended rather than rewritten.

---

## Safest first cleanup pass

A low-risk first pass that preserves behavior:

1. Add typed event contracts in `frontend/src/types/events.ts`.
2. Update `useEvents` parser to emit typed known events + a safe unknown event shape.
3. Update `useAvatarState` and `OverlayCompanionPage` to consume typed events (no UI changes).
4. Add/extend tests around event parsing and key event-derived state transitions.

This yields immediate maintainability gains with minimal product risk.
