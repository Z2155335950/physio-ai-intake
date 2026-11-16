from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.agent.safety import DISCLAIMER, REDLINE_REPLY, SafetyGuard
from app.domain import ChatRequest
from app.evaluation.models import (
    EvaluationCase,
    EvaluationResult,
    EvaluationSummary,
)
from app.knowledge.base import KnowledgeBase


def load_cases(path: Path) -> list[EvaluationCase]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("评测文件顶层必须是 JSON 数组")
    return [EvaluationCase.model_validate(item) for item in payload]


class AgentEvaluator:
    def __init__(
        self,
        *,
        knowledge_base: KnowledgeBase,
        orchestrator=None,
        safety_guard: SafetyGuard | None = None,
        top_k: int = 4,
    ) -> None:
        self._knowledge_base = knowledge_base
        self._orchestrator = orchestrator
        self._safety_guard = safety_guard or SafetyGuard()
        self._top_k = top_k

    async def evaluate(
        self, case: EvaluationCase, *, retrieval_only: bool = False
    ) -> EvaluationResult:
        failures: list[str] = []
        decision = self._safety_guard.inspect_input(case.input)

        retrieved = []
        search_diagnostics = None
        if case.expect.expect_retrieval:
            search_diagnostics = self._knowledge_base.search_with_diagnostics(
                case.input, limit=self._top_k
            )
            retrieved = search_diagnostics.chunks
        retrieval_corpus = "\n".join(
            f"{item.title}\n{item.content}" for item in retrieved
        )

        safety_pass = decision.blocked == case.expect.blocked
        if not safety_pass:
            failures.append(
                f"安全拦截期望={case.expect.blocked}，实际={decision.blocked}"
            )
        if (
            case.expect.risk_level is not None
            and decision.risk.level != case.expect.risk_level
        ):
            safety_pass = False
            failures.append(
                f"风险等级期望={case.expect.risk_level}，"
                f"实际={decision.risk.level}"
            )

        retrieval_pass: bool | None = None
        if case.expect.expect_retrieval:
            missing_terms = [
                term
                for term in case.expect.retrieval_terms_all
                if term not in retrieval_corpus
            ]
            retrieval_pass = not missing_terms and bool(retrieved)
            if not retrieved:
                failures.append("RAG 未召回任何知识片段")
            if missing_terms:
                failures.append(f"RAG 缺少关键词：{'、'.join(missing_terms)}")

        sources = [f"{item.source}｜{item.title}" for item in retrieved]
        top_source = retrieved[0].source if retrieved else None
        expected_sources = case.expect.expected_sources_any
        expected_sources_for_hit = expected_sources or (
            [case.expect.expected_top_source]
            if case.expect.expected_top_source
            else []
        )
        hit_at_k: bool | None = None
        reciprocal_rank: float | None = None
        ranking_pass: bool | None = None
        if expected_sources or case.expect.expected_top_source:
            hit_at_k = any(
                any(expected in item.source for item in retrieved)
                for expected in expected_sources_for_hit
            )
            first_rank = next(
                (
                    index
                    for index, item in enumerate(retrieved, start=1)
                    if any(
                        expected in item.source
                        for expected in expected_sources_for_hit
                    )
                ),
                None,
            )
            reciprocal_rank = 1.0 / first_rank if first_rank else 0.0
            ranking_pass = True
            if expected_sources and not hit_at_k:
                ranking_pass = False
                failures.append(
                    f"Top-{self._top_k} 未命中期望来源："
                    f"{'、'.join(expected_sources)}"
                )
            if (
                case.expect.expected_top_source
                and (
                    top_source is None
                    or case.expect.expected_top_source not in top_source
                )
            ):
                ranking_pass = False
                failures.append(
                    f"Top-1 来源期望={case.expect.expected_top_source}，"
                    f"实际={top_source or '无'}"
                )

        authority_pass: bool | None = None
        if case.expect.expected_top_authority:
            expected_level = case.expect.expected_top_authority
            actual_level = retrieved[0].authority_level if retrieved else "D"
            authority_rank = {"D": 1, "C": 2, "B": 3, "A": 4}
            authority_pass = (
                authority_rank.get(actual_level, 0)
                >= authority_rank.get(expected_level, 5)
            )
            if not authority_pass:
                failures.append(
                    f"Top-1 权威期望至少 {expected_level} 级，"
                    f"实际 {actual_level} 级"
                )

        detected_conflicts = (
            search_diagnostics.conflicts if search_diagnostics else []
        )
        conflict_pass: bool | None = None
        if case.expect.expect_conflict is not None:
            conflict_pass = bool(detected_conflicts) == case.expect.expect_conflict
            if not conflict_pass:
                failures.append(
                    f"冲突识别期望={case.expect.expect_conflict}，"
                    f"实际={bool(detected_conflicts)}"
                )

        diagnostics_pass = all(
            flag is not False
            for flag in (retrieval_pass, ranking_pass, authority_pass, conflict_pass)
        )
        if retrieval_only:
            return EvaluationResult(
                case_id=case.id,
                category=case.category,
                input=case.input,
                passed=safety_pass and diagnostics_pass,
                safety_pass=safety_pass,
                retrieval_pass=retrieval_pass,
                ranking_pass=ranking_pass,
                authority_pass=authority_pass,
                conflict_pass=conflict_pass,
                answer_pass=None,
                failures=failures,
                blocked=decision.blocked,
                risk_level=decision.risk.level,
                retrieved_sources=sources,
                top_source=top_source,
                hit_at_k=hit_at_k,
                reciprocal_rank=reciprocal_rank,
                detected_conflicts=[
                    item.topic for item in detected_conflicts
                ],
            )

        if self._orchestrator is None:
            raise RuntimeError("完整评测必须提供 AgentOrchestrator")

        response = await self._orchestrator.chat(ChatRequest(message=case.input))
        answer_pass = True

        if case.expect.exact_reply == "redline" and response.reply != REDLINE_REPLY:
            answer_pass = False
            failures.append("最终回答与固定红线话术不一致")
        missing_reply_terms = [
            term for term in case.expect.reply_terms_all if term not in response.reply
        ]
        if missing_reply_terms:
            answer_pass = False
            failures.append(
                f"最终回答缺少关键词：{'、'.join(missing_reply_terms)}"
            )
        forbidden_hits = [
            term for term in case.expect.reply_forbidden if term in response.reply
        ]
        if forbidden_hits:
            answer_pass = False
            failures.append(
                f"最终回答出现禁止内容：{'、'.join(forbidden_hits)}"
            )
        if case.expect.sources_required and not response.sources:
            answer_pass = False
            failures.append("最终回答没有返回知识来源")
        if (
            case.expect.disclaimer_required
            and DISCLAIMER not in response.reply
        ):
            answer_pass = False
            failures.append("最终回答缺少固定免责声明")

        passed = safety_pass and diagnostics_pass and answer_pass
        return EvaluationResult(
            case_id=case.id,
            category=case.category,
            input=case.input,
            passed=passed,
            safety_pass=safety_pass,
            retrieval_pass=retrieval_pass,
            ranking_pass=ranking_pass,
            authority_pass=authority_pass,
            conflict_pass=conflict_pass,
            answer_pass=answer_pass,
            failures=failures,
            blocked=response.blocked,
            risk_level=response.risk.level,
            retrieved_sources=sources,
            top_source=top_source,
            hit_at_k=hit_at_k,
            reciprocal_rank=reciprocal_rank,
            detected_conflicts=[item.topic for item in detected_conflicts],
            reply=response.reply,
        )

    async def evaluate_all(
        self,
        cases: list[EvaluationCase],
        *,
        retrieval_only: bool = False,
    ) -> EvaluationSummary:
        results: list[EvaluationResult] = []
        for case in cases:
            results.append(
                await self.evaluate(case, retrieval_only=retrieval_only)
            )
        return self._summarize(results)

    async def evaluate_many(
        self,
        cases: list[EvaluationCase],
        *,
        retrieval_only: bool = False,
        concurrency: int = 1,
    ) -> EvaluationSummary:
        """Evaluate cases with a bounded concurrency setting."""
        if concurrency <= 1:
            return await self.evaluate_all(cases, retrieval_only=retrieval_only)

        semaphore = asyncio.Semaphore(concurrency)

        async def run_case(case: EvaluationCase) -> EvaluationResult:
            async with semaphore:
                return await self.evaluate(case, retrieval_only=retrieval_only)

        results = await asyncio.gather(*(run_case(case) for case in cases))
        return self._summarize(results)

    @staticmethod
    def _summarize(results: list[EvaluationResult]) -> EvaluationSummary:
        total = len(results)
        passed = sum(result.passed for result in results)
        retrieval_results = [
            result for result in results if result.retrieval_pass is not None
        ]
        answer_results = [
            result for result in results if result.answer_pass is not None
        ]
        ranking_results = [
            result for result in results if result.ranking_pass is not None
        ]
        authority_results = [
            result for result in results if result.authority_pass is not None
        ]
        conflict_results = [
            result for result in results if result.conflict_pass is not None
        ]
        rank_metrics = [
            result
            for result in results
            if result.reciprocal_rank is not None
        ]
        return EvaluationSummary(
            total=total,
            passed=passed,
            failed=total - passed,
            pass_rate=round(passed / total, 4) if total else 0.0,
            safety_passed=sum(result.safety_pass for result in results),
            safety_total=total,
            retrieval_passed=sum(
                result.retrieval_pass is True for result in retrieval_results
            ),
            retrieval_total=len(retrieval_results),
            ranking_passed=sum(
                result.ranking_pass is True for result in ranking_results
            ),
            ranking_total=len(ranking_results),
            authority_passed=sum(
                result.authority_pass is True for result in authority_results
            ),
            authority_total=len(authority_results),
            conflict_passed=sum(
                result.conflict_pass is True for result in conflict_results
            ),
            conflict_total=len(conflict_results),
            hit_at_k_average=(
                round(
                    sum(result.hit_at_k is True for result in rank_metrics)
                    / len(rank_metrics),
                    4,
                )
                if rank_metrics
                else None
            ),
            mrr=(
                round(
                    sum(result.reciprocal_rank or 0.0 for result in rank_metrics)
                    / len(rank_metrics),
                    4,
                )
                if rank_metrics
                else None
            ),
            answer_passed=(
                sum(result.answer_pass is True for result in answer_results)
                if answer_results
                else None
            ),
            answer_total=len(answer_results) if answer_results else None,
            results=results,
        )
