# Security Hardening Changes

## What was changed

- Added a restrictive Tauri Content Security Policy (CSP) in `frontend/src-tauri/tauri.conf.json`.
- Hardened backend defaults in `backend/app/config/settings.py`:
  - bind host defaults to `127.0.0.1`
  - default CORS origins changed from wildcard to explicit localhost/tauri origins
  - added explicit WebSocket origin allowlist setting
- Hardened backend API server in `backend/app/main.py`:
  - restricted CORS methods/headers
  - added global error handler returning generic 500 responses
  - added WebSocket origin validation and deny-by-default behavior for unknown origins
- Added SSRF guardrails in `backend/app/services/page_fetcher.py`:
  - reject non-http(s) URLs
  - reject localhost and private/link-local/reserved IP targets
  - avoid logging raw remote fetch errors that may leak internals
- Reduced sensitive error leakage in `backend/app/routers/control.py` for transcription failures.
- Added renderer-side link hardening in `frontend/src/main.tsx`:
  - block `javascript:` and `data:` URL schemes in anchors
  - block `window.open` in Tauri runtime
- Updated source link attributes in `frontend/src/components/WebAnswerTextbox.tsx` to include `noopener`, `noreferrer`, and `referrerPolicy="no-referrer"`.
- Added `.env.example` and expanded `.gitignore` for env files, runtime data, and logs.
- Removed tracked runtime identity memory file from source control and replaced with `.gitkeep`.
- Added CI security/build workflow at `.github/workflows/security-ci.yml` for lint, build, tests, dependency audits, and secret scanning.
- Added `SECURITY.md` policy and reporting guidance.

## Remaining risks / tradeoffs

- Tauri renderer still imports `@tauri-apps/api` directly (normal for Tauri), so capability permissions remain critical.
- CSP currently permits localhost API/WebSocket connectivity for local sidecar architecture.
- Runtime identity store still contains sensitive user data at runtime; it is no longer tracked in git, but local disk protection remains an operational requirement.

## Recommended next steps

1. Add end-to-end security tests validating blocked origins and blocked disallowed fetch URLs.
2. Consider encrypting sensitive local identity store data at rest (platform keyring-backed key).
3. Add signed update strategy documentation if auto-update is introduced.
4. Add centralized redaction filters for logs that may include user-provided text.
