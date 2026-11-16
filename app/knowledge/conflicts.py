from __future__ import annotations

import re
from dataclasses import dataclass

from app.knowledge.base import KnowledgeConflict, RetrievedChunk


_TOPICS = (
    "正骨",
    "复位",
    "扳法",
    "拉伸",
    "热敷",
    "艾灸",
    "膏药",
    "拔罐",
    "刮痧",
)
_NEGATIVE_RE = re.compile(
    r"禁止|严禁|不能|不可|避免|不适合|不安排|不考虑|禁用|慎用|不宜|不要|不做"
)
_POSITIVE_RE = re.compile(r"可以|可做|适合|允许|建议|常规|正常")
_CONDITIONAL_RE = re.compile(
    r"\d+\s*[/／]\s*\d+|[<>＞＜]|孕早期|轻度|中度|重度|控制稳定|"
    r"控制不稳|恢复良好|急性期|必要时|视情况"
)


@dataclass(frozen=True)
class _Direction:
    topic: str
    direction: str
    conditional: bool


class ConflictDetector:
    def detect(
        self, chunks: list[RetrievedChunk], query: str = ""
    ) -> list[KnowledgeConflict]:
        target_topics = {topic for topic in _TOPICS if topic in query}
        if not target_topics:
            return []
        by_source: dict[str, list[_Direction]] = {}
        for chunk in chunks:
            directions = [
                item
                for item in self._directions(chunk.content)
                if item.topic in target_topics
            ]
            if directions:
                by_source[chunk.source] = directions

        conflicts: list[KnowledgeConflict] = []
        source_names = list(by_source)
        for index, left_source in enumerate(source_names):
            for right_source in source_names[index + 1 :]:
                left = by_source[left_source]
                right = by_source[right_source]
                for left_topic in left:
                    for right_topic in right:
                        if left_topic.topic != right_topic.topic:
                            continue
                        if left_topic.direction == right_topic.direction:
                            continue
                        if (
                            left_topic.conditional
                            or right_topic.conditional
                        ):
                            # Conditional statements can coexist; surface them
                            # for review but do not label them as absolute conflicts.
                            resolution = (
                                "来源包含条件限制，不直接判定绝对冲突；"
                                "先核对血压、病程、体质等条件，再采用更保守表述。"
                            )
                        else:
                            resolution = (
                                "采用权威等级更高且限制更强的来源；"
                                "若同等级，不扩大适用范围并明确提示来源不一致。"
                            )
                        involved = tuple(
                            sorted(
                                (left_source, right_source),
                                key=lambda source: self._authority_rank(
                                    chunks, source
                                ),
                                reverse=True,
                            )
                        )
                        preferred = (
                            left_source
                            if left_topic.direction == "restrict"
                            else right_source
                        )
                        conflicts.append(
                            KnowledgeConflict(
                                topic=left_topic.topic,
                                preferred_source=preferred,
                                preferred_authority=self._authority_level(
                                    chunks, preferred
                                ),
                                involved_sources=involved,
                                resolution=resolution,
                                conditional=(
                                    left_topic.conditional
                                    or right_topic.conditional
                                ),
                            )
                        )
                        break
        return self._deduplicate(conflicts)

    @staticmethod
    def _directions(content: str) -> list[_Direction]:
        directions: list[_Direction] = []
        for topic in _TOPICS:
            for match in re.finditer(re.escape(topic), content):
                window = content[max(0, match.start() - 45) : match.end() + 55]
                negative = bool(_NEGATIVE_RE.search(window))
                positive = bool(_POSITIVE_RE.search(window))
                conditional = bool(_CONDITIONAL_RE.search(window))
                if negative and not positive:
                    direction = "restrict"
                elif positive and not negative:
                    direction = "permit"
                else:
                    continue
                item = _Direction(topic, direction, conditional)
                if item not in directions:
                    directions.append(item)
        return directions

    @staticmethod
    def _authority_rank(chunks: list[RetrievedChunk], source: str) -> int:
        return max(
            (chunk.authority_rank for chunk in chunks if chunk.source == source),
            default=0,
        )

    @staticmethod
    def _authority_level(chunks: list[RetrievedChunk], source: str) -> str:
        matching = [chunk for chunk in chunks if chunk.source == source]
        if not matching:
            return "D"
        return max(matching, key=lambda chunk: chunk.authority_rank).authority_level

    @staticmethod
    def _deduplicate(
        conflicts: list[KnowledgeConflict],
    ) -> list[KnowledgeConflict]:
        seen: set[tuple[str, tuple[str, ...]]] = set()
        result: list[KnowledgeConflict] = []
        for conflict in conflicts:
            key = (conflict.topic, conflict.involved_sources)
            if key not in seen:
                result.append(conflict)
                seen.add(key)
        return result

