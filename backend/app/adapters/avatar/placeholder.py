from typing import Any

from app.adapters.avatar.base import AvatarClient


class PlaceholderAvatarClient(AvatarClient):
    def __init__(self) -> None:
        self.current_state = "idle"
        self.current_expression = "neutral"

    async def initialize(self) -> list[dict[str, Any]]:
        return [
            {"event_type": "model_ready", "payload": {"model": "placeholder-3d-shell"}},
            {
                "event_type": "state_change",
                "payload": {"state": self.current_state},
            },
        ]

    async def dispatch(self, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = payload or {}

        if event_type == "state_change":
            self.current_state = str(body.get("state", self.current_state))
        if event_type == "expression_change":
            self.current_expression = str(body.get("expression", self.current_expression))

        return {
            "event_type": event_type,
            "state": self.current_state,
            "expression": self.current_expression,
            **body,
        }
