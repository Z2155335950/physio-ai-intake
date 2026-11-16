from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.knowledge.base import (
    KnowledgeSearchResult,
    RetrievedChunk,
)
from app.knowledge.conflicts import ConflictDetector
from app.knowledge.policy import KnowledgePolicy, SourceAuthority
from app.knowledge.reranker import AuthorityReranker
from app.text import tokenize


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(slots=True)
class _Chunk:
    chunk_id: str
    title: str
    source: str
    content: str
    tokens: list[str]
    term_frequencies: Counter[str]
    authority: SourceAuthority


class MarkdownKnowledgeBase:
    """Small in-memory BM25 index over section-level markdown chunks."""

    def __init__(self, chunks: list[_Chunk], document_count: int) -> None:
        self._chunks = chunks
        self._document_count = document_count
        self._average_length = (
            sum(len(chunk.tokens) for chunk in chunks) / len(chunks) if chunks else 0
        )
        self._document_frequencies = self._build_document_frequencies(chunks)

    @classmethod
    def from_directory(
        cls,
        directory: Path,
        *,
        policy_file: Path | None = None,
    ) -> "MarkdownKnowledgeBase":
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
        resolved_policy_file = policy_file
        if resolved_policy_file is None:
            candidate = directory.parent / "knowledge_policy.json"
            resolved_policy_file = candidate if candidate.exists() else None
        policy = KnowledgePolicy.load(resolved_policy_file)

        files = sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() == ".md"
        )
        chunks: list[_Chunk] = []
        used_files = 0
        for path in files:
            if any(part.startswith(".") for part in path.relative_to(directory).parts):
                continue
            used_files += 1
            chunks.extend(cls._chunk_file(path, directory, policy))

        return cls(chunks=chunks, document_count=used_files)

    @property
    def document_count(self) -> int:
        return self._document_count

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    def search(self, query: str, limit: int = 4) -> list[RetrievedChunk]:
        return self.search_with_diagnostics(query, limit=limit).chunks

    def search_with_diagnostics(
        self, query: str, limit: int = 4
    ) -> KnowledgeSearchResult:
        query_tokens = tokenize(query)
        if not query_tokens or not self._chunks:
            return KnowledgeSearchResult(
                chunks=[], conflicts=[], candidate_count=0
            )

        unique_query_tokens = list(dict.fromkeys(query_tokens))
        scored: list[tuple[float, _Chunk]] = []
        total_chunks = len(self._chunks)
        average_length = self._average_length or 1.0

        for chunk in self._chunks:
            score = 0.0
            for token in unique_query_tokens:
                frequency = chunk.term_frequencies.get(token, 0)
                if not frequency:
                    continue
                document_frequency = self._document_frequencies.get(token, 0)
                inverse_document_frequency = math.log(
                    1 + (total_chunks - document_frequency + 0.5)
                    / (document_frequency + 0.5)
                )
                denominator = frequency + 1.2 * (
                    1 - 0.75 + 0.75 * len(chunk.tokens) / average_length
                )
                score += inverse_document_frequency * (
                    frequency * 2.2 / denominator
                )

            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            return KnowledgeSearchResult(
                chunks=[], conflicts=[], candidate_count=0
            )

        # Recall is deliberately broader than the answer window. The reranker
        # can then recover authoritative safety or policy sources even when
        # their BM25 score is not the absolute highest.
        minimum_candidate_score = max(1.5, scored[0][0] * 0.18)
        candidate_limit = max(12, limit * 4)
        candidates = [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                title=chunk.title,
                source=chunk.source,
                content=chunk.content,
                score=round(score, 4),
                authority_level=chunk.authority.authority_level,
                authority_rank=chunk.authority.authority_rank,
                source_type=chunk.authority.source_type,
                authority_label=chunk.authority.label,
                retrieval_score=round(score, 6),
                rerank_score=0.0,
            )
            for score, chunk in scored[:candidate_limit]
            if score >= minimum_candidate_score
        ]
        reranked_window = AuthorityReranker().rerank(
            query,
            candidates,
            limit=max(limit * 2, 8),
        )
        conflicts = ConflictDetector().detect(reranked_window, query)
        return KnowledgeSearchResult(
            chunks=reranked_window[:limit],
            conflicts=conflicts,
            candidate_count=len(candidates),
        )

    @staticmethod
    def _build_document_frequencies(chunks: list[_Chunk]) -> dict[str, int]:
        frequencies: Counter[str] = Counter()
        for chunk in chunks:
            frequencies.update(chunk.term_frequencies.keys())
        return dict(frequencies)

    @classmethod
    def _chunk_file(
        cls, path: Path, root: Path, policy: KnowledgePolicy
    ) -> list[_Chunk]:
        text = path.read_text(encoding="utf-8-sig")
        source = str(path.relative_to(root))
        lines = text.splitlines()

        sections: list[tuple[str, list[str]]] = []
        heading_stack: dict[int, str] = {}
        current_title = path.stem
        current_lines: list[str] = []

        def finish_current() -> None:
            if cls._has_body(current_lines):
                sections.append((current_title, list(current_lines)))

        for line in lines:
            heading = _HEADING_RE.match(line)
            if heading:
                level = len(heading.group(1))
                title = heading.group(2).strip()

                # Levels 1-3 define retrieval boundaries. Deeper headings stay
                # inside their parent chunk so short templates are not split
                # into heading-only fragments.
                if level <= 3:
                    finish_current()
                    for known_level in [
                        item for item in heading_stack if item >= level
                    ]:
                        del heading_stack[known_level]
                    heading_stack[level] = title
                    current_title = " > ".join(
                        heading_stack[item] for item in sorted(heading_stack)
                    )
                    current_lines = []
                else:
                    if not current_lines and heading_stack:
                        current_title = " > ".join(
                            heading_stack[item] for item in sorted(heading_stack)
                        )
                    current_lines.append(line)
            elif current_lines or any(
                item.strip() and not _HEADING_RE.match(item) for item in [line]
            ):
                current_lines.append(line)

        finish_current()

        chunks: list[_Chunk] = []
        for section_index, (title, section_lines) in enumerate(sections):
            body = "\n".join(section_lines).strip()
            if not body:
                continue
            for part_index, part in enumerate(cls._split_long_section(body)):
                chunk_id = f"{source}::{section_index}::{part_index}"
                searchable_text = f"{title}\n{part}"
                tokens = tokenize(searchable_text)
                chunks.append(
                    _Chunk(
                        chunk_id=chunk_id,
                        title=title,
                        source=source,
                        content=part,
                        tokens=tokens,
                        term_frequencies=Counter(tokens),
                        authority=policy.resolve(source),
                    )
                )
        return chunks

    @staticmethod
    def _has_body(lines: list[str]) -> bool:
        return any(
            line.strip() and not _HEADING_RE.match(line.strip())
            for line in lines
        )

    @staticmethod
    def _split_long_section(text: str, max_chars: int = 1800) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        paragraphs = re.split(r"\n(?=(?:#{1,6}\s|[-*]\s|\d+\.\s|Q：|【))", text)
        parts: list[str] = []
        current: list[str] = []
        current_length = 0
        for paragraph in paragraphs:
            paragraph_length = len(paragraph)
            if current and current_length + paragraph_length > max_chars:
                parts.append("\n".join(current).strip())
                current = []
                current_length = 0
            current.append(paragraph)
            current_length += paragraph_length + 1
        if current:
            parts.append("\n".join(current).strip())
        return [part for part in parts if part]

