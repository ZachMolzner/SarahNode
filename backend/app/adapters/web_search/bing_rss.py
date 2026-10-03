from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

import httpx

from app.adapters.web_search.base import SearchResult, WebSearchProvider


_TAG_RE = re.compile(r"<[^>]+>")


class BingRSSSearchProvider(WebSearchProvider):
    """No-key web search provider using Bing's RSS search output."""

    provider_name = "bing_rss"

    def __init__(self, timeout_seconds: float = 6.0) -> None:
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _clean_text(value: str | None) -> str:
        text = html.unescape(str(value or ""))
        text = _TAG_RE.sub(" ", text)
        return " ".join(text.split())

    @classmethod
    def _parse_feed(cls, xml_text: str, max_results: int) -> list[SearchResult]:
        root = ET.fromstring(xml_text)
        results: list[SearchResult] = []
        for idx, item in enumerate(root.findall(".//item")[:max_results], start=1):
            title = cls._clean_text(item.findtext("title"))
            url = cls._clean_text(item.findtext("link"))
            snippet = cls._clean_text(item.findtext("description"))
            if not url.startswith(("http://", "https://")):
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    provider=cls.provider_name,
                    rank=idx,
                )
            )
        return results

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        params = {
            "q": query,
            "format": "rss",
            "count": max(1, min(max_results, 10)),
        }
        headers = {
            "Accept": "application/rss+xml, application/xml, text/xml",
            "User-Agent": "SarahNode/0.5 (+local technical assistant)",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = await client.get("https://www.bing.com/search", params=params)
            response.raise_for_status()

        return self._parse_feed(response.text, max_results)
