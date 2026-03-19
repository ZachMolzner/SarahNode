from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str
    rank: int


class WebSearchProvider(ABC):
    provider_name: str = "unknown"

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        raise NotImplementedError
