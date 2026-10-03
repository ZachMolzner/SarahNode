from app.services.capability_router import CapabilityRoute
from app.services.web_browsing_policy import WebBrowsingPolicy


def troubleshooting_route() -> CapabilityRoute:
    return CapabilityRoute(
        intent="it_troubleshooting",
        confidence=0.88,
        requires_web_lookup=False,
        style_hint="Troubleshoot.",
    )


def test_vendor_specific_it_issue_uses_web() -> None:
    decision = WebBrowsingPolicy().decide(
        "Zebra driver error code after a firmware update",
        troubleshooting_route(),
    )
    assert decision.should_browse is True
    assert decision.reason == "current_vendor_support_needed"


def test_generic_it_failure_does_not_browse_without_freshness_need() -> None:
    decision = WebBrowsingPolicy().decide(
        "My laptop won't boot",
        troubleshooting_route(),
    )
    assert decision.should_browse is False
