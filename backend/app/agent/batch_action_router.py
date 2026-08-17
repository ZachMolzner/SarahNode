from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.agent.confirmed_action_router import ConfirmedActionRequest, parse_confirmed_action
from app.agent.desktop_action_router import DesktopActionRequest, parse_desktop_action


_ACTION_START = re.compile(
    r"(?:open|launch|start|focus|switch\s+to|bring|go\s+to|create|make|rename|move|delete|remove|recycle|close|quit|exit|kill|terminate|force\s+close|force\s+quit)\b",
    re.IGNORECASE,
)
_SEPARATOR = re.compile(
    r"(?:,\s*(?:and\s+)?|\s+(?:and\s+then|then|and)\s+)(?=(?:open|launch|start|focus|switch\s+to|bring|go\s+to|create|make|rename|move|delete|remove|recycle|close|quit|exit|kill|terminate|force\s+close|force\s+quit)\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PlannedAction:
    tool_name: str
    arguments: dict[str, Any]
    summary: str
    kind: str
    requires_confirmation: bool
    subject: str = ""


@dataclass(frozen=True, slots=True)
class ActionPlan:
    actions: tuple[PlannedAction, ...]

    @property
    def requires_confirmation(self) -> bool:
        return any(action.requires_confirmation for action in self.actions)


@dataclass(frozen=True, slots=True)
class PendingActionPlan:
    plan: ActionPlan
    created_at: datetime
    expires_at: datetime


class PendingActionPlanStore:
    def __init__(self, ttl_seconds: int = 180) -> None:
        self.ttl = timedelta(seconds=max(30, ttl_seconds))
        self._pending: dict[str, PendingActionPlan] = {}

    def stage(self, user_id: str, plan: ActionPlan) -> PendingActionPlan:
        now = datetime.now(timezone.utc)
        pending = PendingActionPlan(plan=plan, created_at=now, expires_at=now + self.ttl)
        self._pending[user_id] = pending
        return pending

    def get(self, user_id: str) -> PendingActionPlan | None:
        pending = self._pending.get(user_id)
        if pending is None:
            return None
        if pending.expires_at <= datetime.now(timezone.utc):
            self._pending.pop(user_id, None)
            return None
        return pending

    def pop(self, user_id: str) -> PendingActionPlan | None:
        pending = self.get(user_id)
        self._pending.pop(user_id, None)
        return pending

    def cancel(self, user_id: str) -> PendingActionPlan | None:
        return self._pending.pop(user_id, None)


def _strip_leading_assistant_name(text: str) -> str:
    return re.sub(r"^\s*sarah[,:]?\s+", "", text.strip(), count=1, flags=re.IGNORECASE)


def split_action_commands(text: str) -> list[str]:
    """Split an explicit multi-action command without breaking separators inside quotes."""
    raw = _strip_leading_assistant_name(text)
    if not raw:
        return []

    segments: list[str] = []
    start = 0
    index = 0
    quote: str | None = None

    while index < len(raw):
        char = raw[index]
        if char in {'"', "'"}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            index += 1
            continue

        if quote is None and char in {";", "\n"}:
            segment = raw[start:index].strip(" ,")
            if segment:
                segments.append(segment)
            start = index + 1
            index += 1
            continue

        if quote is None:
            match = _SEPARATOR.match(raw, index)
            if match:
                segment = raw[start:index].strip(" ,")
                if segment:
                    segments.append(segment)
                start = match.end()
                index = match.end()
                continue

        index += 1

    final = raw[start:].strip(" ,")
    if final:
        segments.append(final)
    return segments


def _desktop_summary(request: DesktopActionRequest) -> str:
    subject = request.subject.strip() or "that"
    if request.tool_name == "open_app":
        return f"open {subject}"
    if request.tool_name == "focus_app":
        return f"bring {subject} to the front"
    if request.tool_name == "open_path":
        return f"open {subject}"
    if request.tool_name == "open_url":
        return f"open {subject}"
    return request.tool_name


def parse_action_plan(text: str, *, max_actions: int = 8) -> ActionPlan | None:
    segments = split_action_commands(text)
    if len(segments) < 2:
        return None
    if len(segments) > max_actions:
        raise ValueError(f"A single request can contain at most {max_actions} actions")

    actions: list[PlannedAction] = []
    for index, segment in enumerate(segments, start=1):
        confirmed: ConfirmedActionRequest | None
        try:
            confirmed = parse_confirmed_action(segment)
        except Exception as exc:
            raise ValueError(f"Step {index} could not be staged safely: {exc}") from exc

        if confirmed is not None:
            actions.append(
                PlannedAction(
                    tool_name=confirmed.tool_name,
                    arguments=dict(confirmed.arguments),
                    summary=confirmed.summary,
                    kind="confirmed",
                    requires_confirmation=True,
                )
            )
            continue

        desktop = parse_desktop_action(segment)
        if desktop is not None:
            actions.append(
                PlannedAction(
                    tool_name=desktop.tool_name,
                    arguments=dict(desktop.arguments),
                    summary=_desktop_summary(desktop),
                    kind="desktop",
                    requires_confirmation=False,
                    subject=desktop.subject,
                )
            )
            continue

        if not _ACTION_START.match(segment.strip()):
            raise ValueError(f"Step {index} is not a recognized desktop action: {segment}")
        raise ValueError(f"Step {index} is ambiguous or unsupported: {segment}")

    return ActionPlan(actions=tuple(actions))
