# Security Policy

## Supported Versions

SarahNode is currently pre-1.0. Security fixes are applied on the active mainline branch.

## Reporting a Vulnerability

Please do **not** open public issues for sensitive vulnerabilities.

- Email maintainers with reproduction details, affected version/commit, and impact.
- Include proof-of-concept inputs and logs with secrets removed.
- Expect acknowledgement within 3 business days.

## Security Baseline

- Secrets must be supplied through environment variables, never committed in source.
- The desktop app runs as a Tauri app with restrictive CSP and capability permissions.
- Backend CORS/WebSocket origins are allowlisted by default.
- Dependency and secret scanning are enforced in CI.

## Release Security Expectations

- Release artifacts must be built from tagged commits in CI.
- Production distribution should use signed binaries/installers.
- Update channels (if enabled later) must use HTTPS and signed artifacts.

## Operational Hardening Checklist

- Set `ENV=prod` and explicit `CORS_ALLOWED_ORIGINS_RAW`/`ALLOWED_WS_ORIGINS_RAW`.
- Keep `BACKEND_BIND_ALL_INTERFACES=0` unless reverse-proxied and firewalled.
- Rotate API keys regularly and scope them to least privilege.
- Monitor logs for repeated origin rejections and malformed payloads.
