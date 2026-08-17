from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str
    tool_calls: Sequence[ModelToolCall] = field(default_factory=tuple)


class ModelGateway(Protocol):
    async def complete(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[Mapping[str, Any]] = (),
    ) -> ModelResponse: ...
