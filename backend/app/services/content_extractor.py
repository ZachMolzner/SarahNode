from __future__ import annotations

import html
import re


class ContentExtractor:
    def extract_text(self, raw_html: str, max_chars: int) -> str:
        without_noise = re.sub(r"<script[^>]*>.*?</script>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
        without_noise = re.sub(r"<style[^>]*>.*?</style>", " ", without_noise, flags=re.IGNORECASE | re.DOTALL)
        without_noise = re.sub(r"<noscript[^>]*>.*?</noscript>", " ", without_noise, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", without_noise)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) <= max_chars:
            return text
        return text[:max_chars].rsplit(" ", 1)[0] + "…"

    def extract_title(self, raw_html: str) -> str | None:
        match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        title = html.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
        return title or None
