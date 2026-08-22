from __future__ import annotations

import re
from dataclasses import dataclass


class MemorySecretRejected(ValueError):
    """Raised when content that looks like a credential/secret reaches persistence."""


@dataclass(frozen=True, slots=True)
class SecretMatch:
    kind: str


_SECRET_LABEL = (
    r"password|passphrase|passcode|pin|"
    r"api[ _-]?key|secret[ _-]?key|client[ _-]?secret|"
    r"access[ _-]?token|refresh[ _-]?token|auth(?:entication)?[ _-]?token|bearer[ _-]?token|"
    r"recovery[ _-]?(?:code|key)|backup[ _-]?code|one[ _-]?time[ _-]?(?:code|password)|otp|"
    r"private[ _-]?key|ssh[ _-]?key|session[ _-]?(?:token|cookie)|cvv|cvc"
)

# Require an assignment marker so ordinary sentences such as "I use a password manager"
# or "I am learning API key security" are not treated as actual credentials.
_LABELED_SECRET_RE = re.compile(
    rf"\b(?:{_SECRET_LABEL})\b\s*(?:is|=|:)\s*\S+",
    re.IGNORECASE,
)

# Stable memory keys are normalized with underscores by MemoryLearningService. Match
# complete key segments rather than substrings so a key such as "spinning_preference"
# cannot be mistaken for a PIN.
_KEY_NAME_SECRET_RE = re.compile(
    r"(?:^|_)(?:password|passphrase|passcode|pin|api_key|secret_key|client_secret|"
    r"access_token|refresh_token|auth_token|recovery_code|recovery_key|backup_code|"
    r"private_key|session_token|session_cookie|cvv|cvc)(?:_|$)",
    re.IGNORECASE,
)

_PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", re.IGNORECASE)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_GITHUB_TOKEN_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")
_OPENAI_STYLE_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")
_SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
_AWS_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")
_AUTH_HEADER_RE = re.compile(r"\bAuthorization\s*:\s*(?:Bearer|Basic)\s+\S+", re.IGNORECASE)

_FORMAT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key", _PRIVATE_KEY_RE),
    ("authorization_header", _AUTH_HEADER_RE),
    ("jwt", _JWT_RE),
    ("github_token", _GITHUB_TOKEN_RE),
    ("api_key", _OPENAI_STYLE_RE),
    ("slack_token", _SLACK_TOKEN_RE),
    ("aws_access_key", _AWS_ACCESS_KEY_RE),
    ("google_api_key", _GOOGLE_API_KEY_RE),
)

_SESSION_SECRET_PLACEHOLDER = "[credential or secret omitted from session memory]"


def detect_persistent_secret(*, key: str = "", value: str = "") -> SecretMatch | None:
    """Return a coarse secret classification without ever returning the secret value."""
    key_text = str(key or "").strip()
    value_text = str(value or "").strip()
    combined = f"{key_text} {value_text}".strip()
    if not combined:
        return None

    normalized_key = re.sub(r"[\s-]+", "_", key_text.lower()).strip("_")
    if normalized_key and value_text and _KEY_NAME_SECRET_RE.search(normalized_key):
        return SecretMatch("credential_labeled_key")

    if _LABELED_SECRET_RE.search(combined):
        return SecretMatch("credential_labeled_value")

    for kind, pattern in _FORMAT_PATTERNS:
        if pattern.search(combined):
            return SecretMatch(kind)
    return None


def redact_for_session_memory(text: str) -> str:
    """Return a safe rolling-memory copy without preserving credential text."""
    raw = str(text or "")
    if detect_persistent_secret(value=raw) is not None:
        return _SESSION_SECRET_PLACEHOLDER
    return raw


def ensure_memory_safe(*, key: str = "", value: str = "") -> None:
    match = detect_persistent_secret(key=key, value=value)
    if match is not None:
        # Keep the exception generic so logs/tool responses never echo credential text.
        raise MemorySecretRejected(
            "Persistent memory refused content that appears to contain a credential or secret."
        )
