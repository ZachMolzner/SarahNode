# SarahNode Security Audit Report (2026-04-01)

## Findings

### High
1. **No CSP configured in Tauri app** (`csp: null`) allowed wider script/resource execution surface.
2. **Wildcard CORS default (`*`)** allowed broad cross-origin API access in default config.
3. **WebSocket endpoint had no origin checks**, enabling cross-site WS abuse from untrusted origins.
4. **Potential SSRF in web page fetcher** accepted arbitrary URLs and followed redirects.
5. **Tracked runtime identity data in repo** (`backend/app/data/identity_memory.json`) risked accidental data leakage.

### Medium
1. Error paths exposed internal exception details in voice transcription route and websocket events.
2. External links lacked explicit `noopener` hardening.
3. Missing CI security gates (dependency audit + secret scan).

### Low
1. `.gitignore` did not comprehensively cover env variants and runtime artifacts.
2. No centralized documented security policy.

## Fixes Applied

- Configured restrictive Tauri CSP.
- Replaced insecure backend defaults (`0.0.0.0`, wildcard CORS) with localhost and explicit allowlists.
- Added WebSocket origin allowlist validation.
- Added SSRF protections for local/private network URL targets.
- Replaced sensitive error details with generic responses/events.
- Hardened renderer link handling against `javascript:`/`data:` URLs and blocked `window.open` in Tauri runtime.
- Hardened outbound link attributes with `noopener noreferrer` and no-referrer policy.
- Added `.env.example`, expanded `.gitignore`, and removed committed runtime identity data.
- Added CI checks for lint/build/test, dependency audits, and secret scanning.
- Added `SECURITY.md` and security hardening docs.

## Risks Not Yet Fixed

1. Runtime identity store is plaintext on local disk; compromise of host can expose personal memory data.
2. Tauri API exposure is capability-based (not preload-bridge model like Electron); capability review must remain strict per release.
3. No binary signing verification workflow documented in-repo for release gates.

## Recommended Next Steps

1. Encrypt local identity memory at rest (OS keyring or hardware-backed key where available).
2. Add a pre-release checklist that includes capability diff review and CSP regression checks.
3. Add integration tests for CORS/WS origin rejection and SSRF guard behavior.
4. Add release signing/integrity verification policy and automated enforcement in CI/CD.
