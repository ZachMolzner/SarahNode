from app.services.capability_router import CapabilityRouter


def test_it_failure_routes_to_troubleshooting() -> None:
    router = CapabilityRouter()
    route = router.classify("My Zebra printer is not detected over USB.")
    assert route.intent == "it_troubleshooting"


def test_network_failure_routes_to_troubleshooting() -> None:
    router = CapabilityRouter()
    route = router.classify("My laptop can't connect to Wi-Fi.")
    assert route.intent == "it_troubleshooting"


def test_plain_explanation_is_not_forced_into_troubleshooting() -> None:
    router = CapabilityRouter()
    route = router.classify("Explain what DNS does.")
    assert route.intent == "lookup_information"


def test_python_error_stays_coding_help() -> None:
    router = CapabilityRouter()
    route = router.classify("Debug this Python error in my function.")
    assert route.intent == "coding_help"
