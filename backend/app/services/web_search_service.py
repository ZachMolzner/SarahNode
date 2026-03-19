from __future__ import annotations

import logging
from dataclasses import dataclass

from app.adapters.web_search.base import SearchResult, WebSearchProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebSearchStatus:
    enabled: bool
    provider: str
    reason: str


class WebSearchService:
    def __init__(self, provider: WebSearchProvider | None, max_results: int) -> None:
        self.provider = provider
        self.max_results = max(1, max_results)

    @property
    def status(self) -> WebSearchStatus:
        if self.provider is None:
            return WebSearchStatus(enabled=False, provider="none", reason="No provider configured")
        return WebSearchStatus(enabled=True, provider=self.provider.provider_name, reason="Configured")

    async def search(self, query: str) -> list[SearchResult]:
        if self.provider is None:
            logger.info("Web search requested without configured provider")
            return []
        try:
            return await self.provider.search(query=query, max_results=self.max_results)
        except Exception:
            logger.exception("Web search failed")
            return []
