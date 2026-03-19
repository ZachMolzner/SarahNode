from __future__ import annotations

from dataclasses import dataclass

from app.services.capability_router import CapabilityRoute


@dataclass(frozen=True)
class BrowsingDecision:
    should_browse: bool
    reason: str


class WebBrowsingPolicy:
    def decide(self, content: str, capability_route: CapabilityRoute) -> BrowsingDecision:
        text = content.strip().lower()

        if capability_route.intent == "browse_web":
            return BrowsingDecision(True, "explicit_browse_intent")

        freshness_markers = (
            "latest",
            "recent",
            "today",
            "current",
            "release notes",
            "price",
            "pricing",
            "news",
            "version",
            "as of",
        )
        explicit_web_markers = ("search the web", "look up", "google", "online", "web")

        if any(marker in text for marker in explicit_web_markers):
            return BrowsingDecision(True, "explicit_web_request")

        if capability_route.intent in {"lookup_information", "coding_help"} and any(
            marker in text for marker in freshness_markers
        ):
            return BrowsingDecision(True, "freshness_needed")

        return BrowsingDecision(False, "no_freshness_signal")
