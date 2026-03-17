# SarahNode Roadmap (Local-First Assistant + Optional Presence Layer)

## Current baseline

SarahNode currently runs as:

- FastAPI backend for assistant orchestration
- React/Vite frontend for LAN dashboards
- WebSocket event stream for real-time state
- Optional placeholder presence/avatar panel

## Near-term milestones

### Milestone A — Assistant reliability

- Improve memory summaries and session notes
- Add clear provider health diagnostics in UI
- Add structured assistant action logs

### Milestone B — Personal productivity tools

- Notes and task tools
- Calendar integration adapter (opt-in)
- Safer confirmation flow for write actions

### Milestone C — Voice improvements

- Better speech playback controls
- Optional local/offline TTS provider adapter
- Mic input prototype (push-to-talk)

### Milestone D — Optional avatar enhancements

- Keep avatar optional and modular
- Add richer expression mapping from assistant events
- Support plug-in renderer choices without coupling core assistant behavior to avatar tech

## Design principles

- Local-first defaults
- Honest capability reporting (implemented vs placeholder)
- Provider abstraction with safe fallback behavior
- Mobile/tablet/desktop responsive UX
