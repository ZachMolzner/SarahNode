from __future__ import annotations

import re
import webbrowser
from typing import Any, Mapping
from urllib.parse import urlparse

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition


_EXPLICIT_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def normalize_http_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    if not candidate:
        raise ValueError("url is required")

    lowered = candidate.lower()
    explicit_scheme = _EXPLICIT_SCHEME_RE.match(candidate)
    if explicit_scheme and not lowered.startswith(("http://", "https://")):
        raise ValueError("Only http:// and https:// URLs are allowed in the safe launch layer")

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are allowed in the safe launch layer")
    if not parsed.netloc:
        raise ValueError("URL must include a host name")
    if any(character.isspace() for character in parsed.netloc):
        raise ValueError("URL host name is invalid")

    return candidate


async def open_url_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    raw_url = str(arguments.get("url", "")).strip()
    url = normalize_http_url(raw_url)
    opened = bool(webbrowser.open(url, new=2, autoraise=True))
    if not opened:
        raise RuntimeError("The operating system did not accept the URL launch request")
    return {"url": url, "action": "opened"}


def safe_open_url_tool() -> ToolDefinition:
    return ToolDefinition(
        name="open_url",
        description=(
            "Use only when the user explicitly asks Sarah to open or go to a web address now. "
            "Open an http:// or https:// address in the user's default browser. "
            "Never use this tool for hypothetical questions, instructions about how to browse, or non-web URL schemes."
        ),
        handler=open_url_handler,
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
            "additionalProperties": False,
        },
        scopes=frozenset({PermissionScope.WEB_LAUNCH}),
        risk=RiskLevel.LOW,
    )
