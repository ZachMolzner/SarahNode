from __future__ import annotations

from dataclasses import dataclass

from app.adapters.web_search.base import SearchResult
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.page_fetcher import FetchedPage


@dataclass(frozen=True)
class WebAnswerContext:
    checked_web: bool
    provider: str
    search_results: list[SearchResult]
    fetched_pages: list[FetchedPage]
    decision_reason: str

    def source_metadata(self) -> list[dict[str, str]]:
        metadata: list[dict[str, str]] = []
        for result in self.search_results:
            metadata.append(
                {
                    "title": result.title,
                    "url": result.url,
                    "provider": result.provider,
                    "snippet": result.snippet,
                }
            )
        return metadata


class WebAnswerSynthesizer:
    def build_web_prompt(self, message: ChatMessage, context: WebAnswerContext) -> str:
        result_lines = []
        for result in context.search_results[:5]:
            result_lines.append(
                f"[{result.rank}] {result.title}\nURL: {result.url}\nSnippet: {result.snippet}"
            )

        fetched_blocks = []
        for page in context.fetched_pages:
            excerpt = page.extracted_text[:1200]
            fetched_blocks.append(
                f"URL: {page.url}\nTitle: {page.title}\nStatus: {page.fetch_status}\nExtracted content:\n{excerpt}"
            )

        return (
            "You have web evidence. Synthesize a ChatGPT-style answer.\n"
            "Rules:\n"
            "- Start with a direct answer in 1-3 sentences.\n"
            "- Mention that you checked the web.\n"
            "- Use strongest sources first; avoid link dumping.\n"
            "- If evidence is weak/conflicting, say that clearly.\n"
            "- Keep concise unless user asked for detail.\n\n"
            f"User query: {message.content}\n"
            f"Web provider: {context.provider}\n"
            f"Decision reason: {context.decision_reason}\n\n"
            "Search results:\n"
            + "\n\n".join(result_lines)
            + "\n\nFetched pages:\n"
            + "\n\n".join(fetched_blocks)
        )

    def unavailable_reply(self) -> AssistantReply:
        return AssistantReply(
            text=(
                "I couldn’t run live web browsing because no web search provider is configured. "
                "If you add Brave or SerpAPI credentials, I can check current sources and summarize them."
            ),
            emotion="concerned",
            should_speak=True,
        )
