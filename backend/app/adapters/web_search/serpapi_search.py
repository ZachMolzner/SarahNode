from __future__ import annotations

import httpx

from app.adapters.web_search.base import SearchResult, WebSearchProvider


class SerpAPISearchProvider(WebSearchProvider):
    provider_name = "serpapi"

    def __init__(self, api_key: str, timeout_seconds: float = 6.0) -> None:
        if not api_key:
            raise ValueError("SERPAPI_API_KEY must be set for SerpAPI search.")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        params = {
            "q": query,
            "api_key": self.api_key,
            "engine": "google",
            "num": max(1, min(max_results, 10)),
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get("https://serpapi.com/search.json", params=params)
            response.raise_for_status()

        payload = response.json()
        raw_results = payload.get("organic_results", [])

        results: list[SearchResult] = []
        for idx, item in enumerate(raw_results[:max_results], start=1):
            results.append(
                SearchResult(
                    title=str(item.get("title", "")).strip(),
                    url=str(item.get("link", "")).strip(),
                    snippet=str(item.get("snippet", "")).strip(),
                    provider=self.provider_name,
                    rank=idx,
                )
            )

        return [result for result in results if result.url]
