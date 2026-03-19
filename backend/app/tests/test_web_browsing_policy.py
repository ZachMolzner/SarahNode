from app.services.capability_router import CapabilityRoute
from app.services.web_browsing_policy import WebBrowsingPolicy


def test_policy_browses_for_fresh_lookup() -> None:
    policy = WebBrowsingPolicy()
    decision = policy.decide(
        "what is the latest react version",
        CapabilityRoute(
            intent="lookup_information",
            confidence=0.8,
            requires_web_lookup=False,
            style_hint="",
        ),
    )
    assert decision.should_browse is True


def test_policy_skips_static_question() -> None:
    policy = WebBrowsingPolicy()
    decision = policy.decide(
        "explain recursion",
        CapabilityRoute(
            intent="lookup_information",
            confidence=0.8,
            requires_web_lookup=False,
            style_hint="",
        ),
    )
    assert decision.should_browse is False
