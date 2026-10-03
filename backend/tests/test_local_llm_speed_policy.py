from app.adapters.llm.local_openai_compatible import LocalOpenAICompatibleClient
from app.services.capability_router import CapabilityRoute


def route(intent: str) -> CapabilityRoute:
    return CapabilityRoute(
        intent=intent,  # type: ignore[arg-type]
        confidence=0.9,
        requires_web_lookup=False,
        style_hint="test",
    )


def test_simple_explanation_does_not_send_tool_schemas() -> None:
    names = LocalOpenAICompatibleClient._relevant_tool_names(
        "Explain what DNS does.",
        route("lookup_information"),
    )
    assert names == set()


def test_it_troubleshooting_exposes_only_read_only_diagnostics() -> None:
    names = LocalOpenAICompatibleClient._relevant_tool_names(
        "My laptop is slow and memory usage seems high.",
        route("it_troubleshooting"),
    )
    assert {"system_info", "system_resources", "running_processes"}.issubset(names)
    assert "memory_remember" not in names


def test_memory_request_exposes_memory_tools() -> None:
    names = LocalOpenAICompatibleClient._relevant_tool_names(
        "What do you remember about my printer?",
        route("lookup_information"),
    )
    assert {"memory_search", "memory_remember", "memory_update", "memory_forget"}.issubset(names)
