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
_SHARED_VERB_RE = re.compile(
    r"^(open|launch|start|close|quit|exit|kill|terminate|force\s+close|force\s+quit)\s+(.+?)\s*$",
    re.IGNORECASE,
)
_TRAILING_CONJUNCTION_RE = re.compile(r"\s+(?:and\s+then|then|and)\s+", re.IGNORECASE)


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
    """Split explicit multi-action commands without breaking separators inside quotes."""
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


def _split_target_list(value: str) -> list[str]:
    """Split `Opera, Calculator, and Downloads` while respecting quoted names."""
    targets: list[str] = []
    start = 0
    index = 0
    quote: str | None = None

    while index < len(value):
        char = value[index]
        if char in {'"', "'"}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            index += 1
            continue

        if quote is None and char == ",":
            target = value[start:index].strip()
            if target:
                targets.append(target)
            index += 1
            while index < len(value) and value[index].isspace():
                index += 1
            if value[index : index + 4].lower() == "and ":
                index += 4
            start = index
            continue

        if quote is None and value[index : index + 5].lower() == " and ":
            target = value[start:index].strip()
            if target:
                targets.append(target)
            index += 5
            start = index
            continue

        index += 1

    final = value[start:].strip()
    if final:
        targets.append(final)
    return targets


def _can_parse_action(segment: str) -> bool:
    try:
        if parse_confirmed_action(segment) is not None:
            return True
    except Exception:
        return False
    return parse_desktop_action(segment) is not None


def _expand_shared_verb(text: str) -> list[str] | None:
    raw = _strip_leading_assistant_name(text)
    match = _SHARED_VERB_RE.match(raw)
    if not match:
        return None

    verb = " ".join(match.group(1).split())
    targets = _split_target_list(match.group(2))
    if len(targets) < 2:
        return None

    expanded = [f"{verb} {target}" for target in targets]
    # Only treat it as shorthand when every expanded action is independently safe
    # to parse. Otherwise leave the original sentence alone so filenames containing
    # words like "and" are not misinterpreted as a batch.
    if not all(_can_parse_action(segment) for segment in expanded):
        return None
    return expanded


def _unsupported_tail_after_parseable_action(text: str) -> str | None:
    """Detect a likely second command that our strict splitter could not recognize.

    The main splitter only separates on conjunctions when the next token begins a
    known action verb. That protects filenames such as ``Research and Development.docx``.
    But it also means ``Open Opera and dance around`` would otherwise look like one
    sentence and quietly fall out of batch routing. If the text before an unquoted
    conjunction is independently parseable as an action, treat the remainder as an
    attempted second step and reject the whole batch rather than silently ignoring it.
    """
    raw = _strip_leading_assistant_name(text)
    quote: str | None = None
    index = 0
    while index < len(raw):
        char = raw[index]
        if char in {'"', "'"}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            index += 1
            continue

        if quote is None:
            match = _TRAILING_CONJUNCTION_RE.match(raw, index)
            if match:
                left = raw[:index].strip(" ,")
                right = raw[match.end() :].strip(" ,")
                if left and right and _can_parse_action(left):
                    return right
                index = match.end()
                continue
        index += 1
    return None


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
        expanded = _expand_shared_verb(text)
        if expanded is None:
            unsupported_tail = _unsupported_tail_after_parseable_action(text)
            if unsupported_tail is not None:
                raise ValueError(f"Step 2 is not a recognized desktop action: {unsupported_tail}")
            return None
        segments = expanded

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
