from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    title: str
    source: str
    content: str
    score: float
    authority_level: str = "D"
    authority_rank: int = 0
    source_type: str = "unclassified"
    authority_label: str = "未分级来源"
    retrieval_score: float = 0.0
    rerank_score: float = 0.0


@dataclass(frozen=True, slots=True)
class KnowledgeConflict:
    topic: str
    preferred_source: str
    preferred_authority: str
    involved_sources: tuple[str, ...]
    resolution: str
    conditional: bool = False


@dataclass(frozen=True, slots=True)
class KnowledgeSearchResult:
    chunks: list[RetrievedChunk]
    conflicts: list[KnowledgeConflict]
    candidate_count: int


class KnowledgeBase(Protocol):
    @property
    def document_count(self) -> int: ...

    @property
    def chunk_count(self) -> int: ...

    def search(self, query: str, limit: int = 4) -> list[RetrievedChunk]: ...

    def search_with_diagnostics(
        self, query: str, limit: int = 4
    ) -> KnowledgeSearchResult: ...

