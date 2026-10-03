import inspect

from app.adapters.llm.local_openai_compatible import LocalOpenAICompatibleClient
from app.config.settings import IT_TROUBLESHOOTING_RULES, TECHNICAL_ACCURACY_RULES, settings


def test_technical_accuracy_rules_are_part_of_sarah_persona() -> None:
    assert "application-layer protocol" in TECHNICAL_ACCURACY_RULES
    assert "Never invent a command" in TECHNICAL_ACCURACY_RULES
    assert "observed evidence from hypotheses" in TECHNICAL_ACCURACY_RULES
    assert TECHNICAL_ACCURACY_RULES in settings.persona_system_prompt


def test_local_live_answer_has_no_active_window_path() -> None:
    source = inspect.getsource(LocalOpenAICompatibleClient._direct_live_answer)
    assert "active_window" not in source
    assert "focused window" not in source


def test_troubleshooting_rules_require_evidence_first_workflow() -> None:
    assert "least disruptive diagnostic step" in IT_TROUBLESHOOTING_RULES
    assert "Separate confirmed observations from likely causes" in IT_TROUBLESHOOTING_RULES
    assert "official documentation" in IT_TROUBLESHOOTING_RULES
