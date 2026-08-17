from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class DesktopActionRequest:
    tool_name: str
    arguments: dict[str, Any]
    subject: str


_URLISH_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}(?:[/:?#].*)?$",
    re.IGNORECASE,
)
_WINDOWS_PATH_RE = re.compile(r"^(?:[a-zA-Z]:[\\/]|~[\\/]|\\\\)")

_KNOWN_FOLDERS = {
    "home",
    "desktop",
    "downloads",
    "documents",
    "pictures",
    "music",
    "videos",
    "sarahnode",
    "sarah node",
    "sarahnode folder",
    "sarah node folder",
    "sarahnode repo",
    "sarah node repo",
}


def _clean_target(value: str) -> str:
    cleaned = value.strip().strip('"').strip("'").strip()
    cleaned = re.sub(r"\s+(?:please|for me)$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def parse_desktop_action(text: str) -> DesktopActionRequest | None:
    """Parse only clear, low-risk desktop launch commands.

    This intentionally does not parse delete/move/rename/kill/install/run-command
    requests. Those belong to stronger permission paths in later phases.
    """
    raw = text.strip()
    if not raw:
        return None

    # Foreground/focus commands are explicit and never launch a new instance.
    focus_patterns = (
        r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:focus|switch to)\s+(.+?)\s*$",
        r"^(?:sarah[,:]?\s+)?(?:please\s+)?bring\s+(.+?)\s+(?:to the front|to front|forward)\s*$",
    )
    for pattern in focus_patterns:
        match = re.match(pattern, raw, re.IGNORECASE)
        if match:
            target = _clean_target(match.group(1))
            if target:
                return DesktopActionRequest("focus_app", {"app": target}, target)

    # Open/launch/start commands. Keep the parser conservative and hand anything
    # more complicated to the model/tool layer instead of guessing.
    match = re.match(
        r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:open|launch|start)\s+(.+?)\s*$",
        raw,
        re.IGNORECASE,
    )
    if match:
        target = _clean_target(match.group(1))
        lowered = target.lower()

        if _URLISH_RE.match(target) or target.lower().startswith(("http://", "https://")):
            return DesktopActionRequest("open_url", {"url": target}, target)

        folder_key = lowered.removeprefix("my ").strip()
        if folder_key in _KNOWN_FOLDERS:
            return DesktopActionRequest("open_path", {"path": folder_key}, target)

        if _WINDOWS_PATH_RE.match(target) or any(sep in target for sep in ("\\", "/")):
            return DesktopActionRequest("open_path", {"path": target}, target)

        # Common file names with an extension can be resolved safely by open_path.
        if re.search(r"\.[a-zA-Z0-9]{1,8}$", target):
            return DesktopActionRequest("open_path", {"path": target}, target)

        return DesktopActionRequest("open_app", {"app": target}, target)

    # "Go to" is reserved for clear web addresses so it cannot be confused with
    # focusing an app or navigating the file system.
    match = re.match(
        r"^(?:sarah[,:]?\s+)?(?:please\s+)?go to\s+(.+?)\s*$",
        raw,
        re.IGNORECASE,
    )
    if match:
        target = _clean_target(match.group(1))
        if _URLISH_RE.match(target) or target.lower().startswith(("http://", "https://")):
            return DesktopActionRequest("open_url", {"url": target}, target)

    return None
