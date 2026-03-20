# SarahNode Current-State Audit (2026-03-20)

This document captures a code-based snapshot of the repository status as of 2026-03-20.

## Snapshot highlights
- Frontend runtime is a React dashboard page that conditionally hides most controls in overlay mode.
- Desktop shell is Tauri 2 with tray integration, summon hotkey, always-on-top and overlay toggles, plus sidecar backend spawn.
- Backend runtime is FastAPI + websocket event stream orchestrator with identity-aware addressing, capability routing, optional web-grounded path, and provider fallback strategy.
- Identity defaults include Zach + Aleena + household with tone directives and optional Aleena “Mama” usage policy.
- Overlay floor behavior, drag/lift/fall/landing, and temporary web answer textbox are implemented in the frontend motion/presence layer.

## Known alignment caveats
- `displayMode` parser default is immersive unless overridden, while persisted desktop defaults are overlay-first.
- Main page/component naming and structure are still dashboard-centric (`DashboardPage` with menu/transcript/settings surfaces).
- Web answer bullet content currently comes from search snippets emitted by the backend web context, not dedicated presentation copy logic.
- Packaging target references `sidecar/sarahnode-backend.exe` for release, but build pipeline still requires explicit sidecar packaging verification.
