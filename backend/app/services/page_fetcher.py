from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.adapters.web_search.base import SearchResult
from app.services.content_extractor import ContentExtractor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchedPage:
    url: str
    title: str
    extracted_text: str
    fetch_status: str
    char_count: int


class PageFetcher:
    def __init__(self, max_pages: int, timeout_seconds: float, max_chars: int) -> None:
        self.max_pages = max(1, max_pages)
        self.timeout_seconds = timeout_seconds
        self.max_chars = max(500, max_chars)
        self.extractor = ContentExtractor()

    async def fetch_pages(self, search_results: list[SearchResult]) -> list[FetchedPage]:
        pages: list[FetchedPage] = []
        for result in search_results[: self.max_pages]:
            pages.append(await self._fetch_page(result.url, fallback_title=result.title))
        return pages

    def _is_disallowed_url(self, raw_url: str) -> bool:
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"https", "http"}:
            return True

        host = (parsed.hostname or "").strip().lower()
        if not host:
            return True

        if host in {"localhost", "127.0.0.1", "::1"}:
            return True

        try:
            ip = ipaddress.ip_address(host)
            return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
        except ValueError:
            return False

    async def _fetch_page(self, url: str, fallback_title: str) -> FetchedPage:
        if self._is_disallowed_url(url):
            return FetchedPage(
                url=url,
                title=fallback_title,
                extracted_text="",
                fetch_status="skipped_disallowed_url",
                char_count=0,
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    return FetchedPage(
                        url=url,
                        title=fallback_title,
                        extracted_text="",
                        fetch_status=f"skipped_non_html:{content_type}",
                        char_count=0,
                    )

                text = self.extractor.extract_text(response.text, max_chars=self.max_chars)
                title = self.extractor.extract_title(response.text) or fallback_title
                return FetchedPage(
                    url=url,
                    title=title,
                    extracted_text=text,
                    fetch_status="ok",
                    char_count=len(text),
                )
        except Exception:
            logger.info("Failed fetching web page")
            return FetchedPage(
                url=url,
                title=fallback_title,
                extracted_text="",
                fetch_status="fetch_failed",
                char_count=0,
            )
