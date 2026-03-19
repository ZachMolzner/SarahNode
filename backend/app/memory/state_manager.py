from collections import deque
from dataclasses import dataclass, field

from app.schemas.chat import ChatMessage


@dataclass
class MemoryState:
    rolling_messages: deque[ChatMessage]
    session_notes: list[str] = field(default_factory=list)
    assistant_state: str = "idle"
    last_reply: str = ""
    last_capability_intent: str = "ask_general"
    last_used_live_web: bool = False
    latest_web_sources: list[dict[str, str]] = field(default_factory=list)
    last_speaker_id: str = "unknown"
    last_speaker_confidence: float = 0.0
    last_address_name: str = "there"
    last_address_mode: str = "unknown"


class MemoryManager:
    def __init__(self, window_size: int) -> None:
        self.state = MemoryState(rolling_messages=deque(maxlen=window_size))

    def add_message(self, message: ChatMessage) -> None:
        self.state.rolling_messages.append(message)

    def add_note(self, note: str) -> None:
        self.state.session_notes.append(note)

    def set_assistant_state(self, assistant_state: str) -> None:
        self.state.assistant_state = assistant_state

    def set_last_reply(self, reply: str) -> None:
        self.state.last_reply = reply

    def set_last_capability(self, intent: str) -> None:
        self.state.last_capability_intent = intent

    def set_last_web_usage(self, used_live_web: bool, sources: list[dict[str, str]] | None = None) -> None:
        self.state.last_used_live_web = used_live_web
        self.state.latest_web_sources = sources or []

    def set_last_identity(self, speaker_id: str, confidence: float, address_name: str, address_mode: str) -> None:
        self.state.last_speaker_id = speaker_id
        self.state.last_speaker_confidence = confidence
        self.state.last_address_name = address_name
        self.state.last_address_mode = address_mode

    def recent_history(self, limit: int = 8) -> list[str]:
        recent = list(self.state.rolling_messages)[-limit:]
        return [f"{m.username}: {m.content}" for m in recent]

    def summarize(self) -> str:
        recent = list(self.state.rolling_messages)[-6:]
        if not recent:
            return "No recent conversation."

        recent_summary = " | ".join(f"{m.username}: {m.content[:60]}" for m in recent)

        if not self.state.session_notes:
            return recent_summary

        notes_summary = " ; ".join(self.state.session_notes[-3:])
        return f"{recent_summary} || notes: {notes_summary}"
