from __future__ import annotations

import httpx

from app.adapters.web_search.base import SearchResult, WebSearchProvider


class BraveSearchProvider(WebSearchProvider):
    provider_name = "brave"

    def __init__(self, api_key: str, timeout_seconds: float = 6.0) -> None:
        if not api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY must be set for Brave search.")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        headers = {"Accept": "application/json", "X-Subscription-Token": self.api_key}
        params = {"q": query, "count": max(1, min(max_results, 20))}

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get("https://api.search.brave.com/res/v1/web/search", headers=headers, params=params)
            response.raise_for_status()

        payload = response.json()
        raw_results = payload.get("web", {}).get("results", [])

        results: list[SearchResult] = []
        for idx, item in enumerate(raw_results[:max_results], start=1):
            results.append(
                SearchResult(
                    title=str(item.get("title", "")).strip(),
                    url=str(item.get("url", "")).strip(),
                    snippet=str(item.get("description", "")).strip(),
                    provider=self.provider_name,
                    rank=idx,
                )
            )

        return [result for result in results if result.url]
