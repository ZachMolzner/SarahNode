from app.services.capability_router import CapabilityRouter


def test_classifies_coding_help() -> None:
    route = CapabilityRouter().classify("Can you help me debug this Python stack trace?")
    assert route.intent == "coding_help"
    assert route.requires_web_lookup is False


def test_classifies_browse_request() -> None:
    route = CapabilityRouter().classify("Please search the web for the latest Rust release")
    assert route.intent == "browse_web"
    assert route.requires_web_lookup is True


def test_classifies_shutdown_command() -> None:
    route = CapabilityRouter().classify("shutdown Sarah now")
    assert route.intent == "shutdown_command"
