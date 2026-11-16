from __future__ import annotations

from dataclasses import replace

from app.knowledge.base import RetrievedChunk
from app.text import tokenize


class AuthorityReranker:
    """Deterministic hybrid reranker for authority, lexical, and intent signals."""

    _INTENT_SOURCE_TYPES: dict[str, dict[str, float]] = {
        "business": {
            "business_policy": 1.0,
            "operational_template": 0.45,
        },
        "safety": {
            "safety_policy": 1.0,
        },
        "communication": {
            "operational_template": 1.0,
            "customer_education": 0.25,
        },
        "assessment": {
            "internal_training": 1.0,
            "operational_template": 0.35,
        },
        "anatomy": {
            "internal_training": 1.0,
        },
    }
    _INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
        "business": (
            "价格",
            "多少钱",
            "套餐",
            "预约",
            "取消",
            "爽约",
            "门店规则",
            "服务说明",
        ),
        "safety": (
            "禁忌",
            "风险",
            "禁止",
            "骨折",
            "高血压",
            "血压",
            "骨质疏松",
            "类风湿",
            "抗凝",
            "夜间",
            "麻木",
            "无力",
            "正骨",
            "复位",
            "扳法",
            "手法",
            "拉伸",
        ),
        "communication": (
            "话术",
            "沟通",
            "拒绝",
            "复诊",
            "怎么跟",
            "标准顺序",
        ),
        "assessment": (
            "评估",
            "查体",
            "压痛",
            "活动受限",
            "肌力",
            "久坐",
            "腰方肌",
            "疼痛性质",
        ),
        "anatomy": (
            "解剖",
            "斜方肌",
            "腰方肌",
            "骶髂",
            "肌肉",
            "关节",
        ),
    }
    _SAFETY_PRECEDENCE_KEYWORDS = (
        "禁忌",
        "风险",
        "能不能做",
        "可以做",
        "适合",
        "注意",
        "血压",
        "高血压",
        "骨质疏松",
        "类风湿",
        "抗凝",
        "骨折",
        "夜间",
        "麻木",
        "无力",
    )

    def rerank(
        self, query: str, candidates: list[RetrievedChunk], limit: int
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []

        top_lexical = max(item.retrieval_score for item in candidates) or 1.0
        query_tokens = {
            token for token in tokenize(query) if len(token) > 1
        }
        intent_weights = self._detect_intents(query)
        priority_source_types: set[str] = set()
        if intent_weights:
            dominant_intent, dominant_weight = max(
                intent_weights.items(), key=lambda item: item[1]
            )
            if dominant_weight >= 0.8:
                priority_source_types = {
                    source_type
                    for source_type, source_weight in self._INTENT_SOURCE_TYPES[
                        dominant_intent
                    ].items()
                    if source_weight >= 0.9
                }
        safety_precedence = (
            "safety" in intent_weights
            and "communication" not in intent_weights
            and any(
                keyword in query
                for keyword in self._SAFETY_PRECEDENCE_KEYWORDS
            )
        )
        ranked: list[RetrievedChunk] = []
        for item in candidates:
            lexical = item.retrieval_score / top_lexical
            authority = item.authority_rank / 100
            haystack = f"{item.title}\n{item.content}".lower()
            coverage = (
                sum(token in haystack for token in query_tokens)
                / len(query_tokens)
                if query_tokens
                else 0.0
            )
            intent_boost = sum(
                weight * self._INTENT_SOURCE_TYPES[intent].get(
                    item.source_type, 0.0
                )
                for intent, weight in intent_weights.items()
            )
            title_bonus = (
                0.08
                if any(
                    token in item.title.lower()
                    for token in query_tokens
                    if len(token) >= 2
                )
                else 0.0
            )
            final_score = (
                0.54 * lexical
                + 0.24 * authority
                + 0.12 * coverage
                + 0.10 * intent_boost
                + title_bonus
            )
            ranked.append(
                replace(
                    item,
                    score=round(final_score, 6),
                    rerank_score=round(final_score, 6),
                )
            )

        ranked.sort(
            key=lambda item: (
                1 if item.source_type in priority_source_types else 0,
                1
                if safety_precedence and item.source_type == "safety_policy"
                else 0,
                item.rerank_score,
            ),
            reverse=True,
        )
        selected: list[RetrievedChunk] = []
        per_source: dict[str, int] = {}
        for item in ranked:
            if per_source.get(item.source, 0) >= 2:
                continue
            selected.append(item)
            per_source[item.source] = per_source.get(item.source, 0) + 1
            if len(selected) >= limit:
                break
        return selected

    def _detect_intents(self, query: str) -> dict[str, float]:
        scores = {
            intent: sum(keyword in query for keyword in keywords)
            for intent, keywords in self._INTENT_KEYWORDS.items()
        }
        total = sum(scores.values())
        if total == 0:
            return {}
        return {
            intent: score / total
            for intent, score in scores.items()
            if score > 0
        }

