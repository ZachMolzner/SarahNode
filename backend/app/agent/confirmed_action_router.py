from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.agent.confirmed_action_tools import (
    _app_executable,
    _known_folder,
    preview_move,
    resolve_existing_mutation_path,
    resolve_new_mutation_path,
)
from app.agent.desktop_action_tools import _normalize_app_name


@dataclass(frozen=True, slots=True)
class ConfirmedActionRequest:
    tool_name: str
    arguments: dict[str, Any]
    summary: str


@dataclass(frozen=True, slots=True)
class PendingConfirmedAction:
    request: ConfirmedActionRequest
    created_at: datetime
    expires_at: datetime


class PendingConfirmedActionStore:
    def __init__(self, ttl_seconds: int = 180) -> None:
        self.ttl = timedelta(seconds=max(30, ttl_seconds))
        self._pending: dict[str, PendingConfirmedAction] = {}

    def stage(self, user_id: str, request: ConfirmedActionRequest) -> PendingConfirmedAction:
        now = datetime.now(timezone.utc)
        pending = PendingConfirmedAction(request=request, created_at=now, expires_at=now + self.ttl)
        self._pending[user_id] = pending
        return pending

    def get(self, user_id: str) -> PendingConfirmedAction | None:
        pending = self._pending.get(user_id)
        if pending is None:
            return None
        if pending.expires_at <= datetime.now(timezone.utc):
            self._pending.pop(user_id, None)
            return None
        return pending

    def pop(self, user_id: str) -> PendingConfirmedAction | None:
        pending = self.get(user_id)
        self._pending.pop(user_id, None)
        return pending

    def cancel(self, user_id: str) -> PendingConfirmedAction | None:
        return self._pending.pop(user_id, None)


_CONFIRM_RE = re.compile(
    r"^(?:yes[,.]?\s*)?(?:confirm(?:\s+it)?|do it|go ahead|proceed|yes)$",
    re.IGNORECASE,
)
_CANCEL_RE = re.compile(
    r"^(?:cancel(?:\s+it)?|no|never\s*mind|nevermind|don't|do not|stop)$",
    re.IGNORECASE,
)
_GENERIC_TARGETS = {
    "a file",
    "a folder",
    "the file",
    "the folder",
    "something",
    "it",
    "that",
}


def is_confirmation(text: str) -> bool:
    return bool(_CONFIRM_RE.match(text.strip()))


def is_cancellation(text: str) -> bool:
    return bool(_CANCEL_RE.match(text.strip()))


def _clean(value: str) -> str:
    cleaned = value.strip().strip('"').strip("'").strip()
    cleaned = re.sub(r"\s+(?:please|for me)$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _folder_plus_name(folder_text: str, name: str) -> Path | None:
    folder = _known_folder(folder_text)
    if folder is None:
        return None
    safe_name = _clean(name)
    if not safe_name or any(separator in safe_name for separator in ("\\", "/")):
        return None
    return (folder / safe_name).resolve()


def parse_confirmed_action(text: str) -> ConfirmedActionRequest | None:
    raw = text.strip()
    if not raw:
        return None

    prefix = r"^(?:sarah[,:]?\s+)?(?:please\s+)?"

    match = re.match(prefix + r"(?:create|make)\s+(?:a\s+)?folder(?:\s+named)?\s+(.+?)\s+in\s+(.+?)\s*$", raw, re.IGNORECASE)
    if match:
        name = _clean(match.group(1))
        folder_text = _clean(match.group(2))
        path = _folder_plus_name(folder_text, name)
        if path is None:
            return None
        resolved = resolve_new_mutation_path(str(path))
        return ConfirmedActionRequest(
            "create_folder",
            {"path": str(resolved)},
            f'create the folder "{resolved}"',
        )

    match = re.match(prefix + r"(?:create|make)\s+(?:a\s+)?folder\s+(.+?)\s*$", raw, re.IGNORECASE)
    if match:
        target = _clean(match.group(1))
        if target.lower() in _GENERIC_TARGETS:
            return None
        if not any(separator in target for separator in ("\\", "/")) and _known_folder(target) is None:
            return None
        resolved = resolve_new_mutation_path(target)
        return ConfirmedActionRequest("create_folder", {"path": str(resolved)}, f'create the folder "{resolved}"')

    match = re.match(
        prefix + r"(?:create|make)\s+(?:a\s+)?file(?:\s+named)?\s+(.+?)\s+in\s+(.+?)(?:\s+with\s+(?:text|content)\s+[\"'](.*)[\"'])?\s*$",
        raw,
        re.IGNORECASE,
    )
    if match:
        name = _clean(match.group(1))
        folder_text = _clean(match.group(2))
        path = _folder_plus_name(folder_text, name)
        if path is None:
            return None
        resolved = resolve_new_mutation_path(str(path))
        content = match.group(3) or ""
        return ConfirmedActionRequest(
            "create_file",
            {"path": str(resolved), "content": content},
            f'create the file "{resolved}"' + (" with the provided text" if content else ""),
        )

    match = re.match(prefix + r"(?:create|make)\s+(?:a\s+)?file\s+(.+?)\s*$", raw, re.IGNORECASE)
    if match:
        target = _clean(match.group(1))
        if target.lower() in _GENERIC_TARGETS:
            return None
        if not any(separator in target for separator in ("\\", "/")):
            return None
        resolved = resolve_new_mutation_path(target)
        return ConfirmedActionRequest("create_file", {"path": str(resolved), "content": ""}, f'create the empty file "{resolved}"')

    match = re.match(prefix + r"rename\s+(.+?)\s+to\s+(.+?)\s*$", raw, re.IGNORECASE)
    if match:
        source_text = _clean(match.group(1))
        destination_text = _clean(match.group(2))
        if source_text.lower() in _GENERIC_TARGETS or destination_text.lower() in _GENERIC_TARGETS:
            return None
        source = resolve_existing_mutation_path(source_text)
        if any(separator in destination_text for separator in ("\\", "/")):
            destination = resolve_new_mutation_path(destination_text)
        else:
            destination = resolve_new_mutation_path(str(source.with_name(destination_text)))
        return ConfirmedActionRequest(
            "move_path",
            {"source": str(source), "destination": str(destination)},
            f'rename "{source}" to "{destination.name}"',
        )

    match = re.match(prefix + r"move\s+(.+?)\s+to\s+(.+?)\s*$", raw, re.IGNORECASE)
    if match:
        source_text = _clean(match.group(1))
        destination_text = _clean(match.group(2))
        if destination_text.lower() in {"recycle bin", "the recycle bin", "trash", "the trash"}:
            source = resolve_existing_mutation_path(source_text)
            return ConfirmedActionRequest(
                "recycle_path",
                {"path": str(source)},
                f'move "{source}" to the Recycle Bin',
            )
        if source_text.lower() in _GENERIC_TARGETS or destination_text.lower() in _GENERIC_TARGETS:
            return None
        source, destination = preview_move(source_text, destination_text)
        return ConfirmedActionRequest(
            "move_path",
            {"source": str(source), "destination": str(destination)},
            f'move "{source}" to "{destination}"',
        )

    match = re.match(prefix + r"(?:delete|remove|recycle)\s+(.+?)\s*$", raw, re.IGNORECASE)
    if match:
        target = _clean(match.group(1))
        if target.lower() in _GENERIC_TARGETS:
            return None
        path = resolve_existing_mutation_path(target)
        return ConfirmedActionRequest(
            "recycle_path",
            {"path": str(path)},
            f'move "{path}" to the Recycle Bin',
        )

    # Force termination is deliberately distinct from a normal close. It can discard
    # unsaved work, so it maps to a HIGH-risk tool and receives its own confirmation.
    match = re.match(prefix + r"(?:force\s+close|force\s+quit|kill|terminate)\s+(.+?)\s*$", raw, re.IGNORECASE)
    if match:
        app = _clean(match.group(1))
        try:
            _app_executable(app)
        except ValueError:
            return None
        if _normalize_app_name(app) in {"explorer", "file explorer"}:
            raise ValueError("Force-closing File Explorer is blocked because it also hosts the Windows shell")
        return ConfirmedActionRequest(
            "terminate_app",
            {"app": app},
            f'force-close {app} and terminate its matching processes',
        )

    match = re.match(prefix + r"(?:close|quit|exit)\s+(.+?)\s*$", raw, re.IGNORECASE)
    if match:
        app = _clean(match.group(1))
        try:
            _app_executable(app)
        except ValueError:
            return None
        return ConfirmedActionRequest("close_app", {"app": app}, f'close {app}')

    return None
