# Changelog

## 2026-03-17

### Refactor: VTuber dashboard -> local assistant control center

- Renamed API primary route from `/api/chat/send` to `/api/assistant/messages`.
- Added `/api/assistant/state` and marked legacy routes deprecated.
- Refactored backend DI/container to explicit provider selection (`LLM_PROVIDER`, `TTS_PROVIDER`) with honest mock fallback behavior.
- Renamed ingestion service to `AssistantIntakeService` and updated message source naming to `web_ui`.
- Updated frontend API contract to assistant routes.
- Reframed dashboard UX copy to assistant-oriented language (conversation/status/presence).
- Replaced heavy VRM runtime path with placeholder avatar/presence panel to keep optional avatar support without hard dependency on unavailable packages.
- Renamed frontend package from `sarahnode-dashboard` to `sarahnode-local-assistant`.
- Rewrote README to match actual implementation, setup, and LAN usage.

### Remaining TODOs

- Add richer assistant memory persistence beyond in-memory rolling window.
- Add authenticated multi-device profile/session controls for non-trusted LAN environments.
- Reintroduce advanced 3D avatar integration behind optional install profile if desired.
