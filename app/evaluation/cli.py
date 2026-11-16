from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.agent.orchestrator import AgentOrchestrator
from app.config import PROJECT_ROOT, get_settings
from app.evaluation.runner import AgentEvaluator, load_cases
from app.knowledge.local_markdown import MarkdownKnowledgeBase
from app.main import create_llm
from app.sessions.memory import InMemorySessionStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="理疗助手安全与 RAG 评测")
    parser.add_argument(
        "--cases",
        type=Path,
        default=PROJECT_ROOT / "data" / "evaluations" / "core_cases.json",
        help="测评集 JSON 文件",
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="只测试安全规则和 RAG 召回，不调用模型",
    )
    parser.add_argument("--case-id", help="只运行指定 Case ID")
    parser.add_argument("--category", help="按分类名称筛选")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--json-output", type=Path, help="保存 JSON 报告")
    return parser.parse_args()


def _mark(flag: bool | None) -> str:
    if flag is None:
        return "-"
    return "PASS" if flag else "FAIL"


async def main() -> int:
    args = parse_args()
    settings = get_settings()
    knowledge_base = MarkdownKnowledgeBase.from_directory(
        settings.knowledge_dir,
        policy_file=settings.knowledge_policy_file,
    )
    cases = load_cases(args.cases)
    if args.case_id:
        cases = [case for case in cases if case.id == args.case_id]
    if args.category:
        cases = [case for case in cases if args.category in case.category]
    if not cases:
        print("没有匹配的测评用例。")
        return 2

    orchestrator = None
    if not args.retrieval_only:
        orchestrator = AgentOrchestrator(
            settings=settings,
            knowledge_base=knowledge_base,
            llm=create_llm(settings),
            session_store=InMemorySessionStore(),
        )

    evaluator = AgentEvaluator(
        knowledge_base=knowledge_base,
        orchestrator=orchestrator,
        top_k=settings.knowledge_top_k,
    )
    summary = await evaluator.evaluate_many(
        cases,
        retrieval_only=args.retrieval_only,
        concurrency=max(1, args.concurrency),
    )

    print(
        f"结果: {summary.passed}/{summary.total} 通过 "
        f"({summary.pass_rate:.1%}) | "
        f"安全 {summary.safety_passed}/{summary.safety_total} | "
        f"RAG {summary.retrieval_passed}/{summary.retrieval_total} | "
        f"排序 {summary.ranking_passed}/{summary.ranking_total} | "
        f"权威 {summary.authority_passed}/{summary.authority_total} | "
        f"冲突 {summary.conflict_passed}/{summary.conflict_total}"
    )
    if summary.hit_at_k_average is not None:
        print(
            f"Hit@K {summary.hit_at_k_average:.1%} | "
            f"MRR {summary.mrr:.4f}"
        )
    if summary.answer_total is not None:
        print(f"回答 {summary.answer_passed}/{summary.answer_total}")
    print()
    print("ID      安全  RAG 排序 权威 冲突 回答  用例")
    print("-" * 92)
    for result in summary.results:
        print(
            f"{result.case_id:<7} {_mark(result.safety_pass):<4} "
            f"{_mark(result.retrieval_pass):<4} "
            f"{_mark(result.ranking_pass):<4} "
            f"{_mark(result.authority_pass):<4} "
            f"{_mark(result.conflict_pass):<4} "
            f"{_mark(result.answer_pass):<4}  {result.input[:36]}"
        )
        for failure in result.failures:
            print(f"      ! {failure}")
        if result.passed and result.reply:
            print(f"      {result.reply[:100].replace(chr(10), ' ')}…")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(
                summary.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nJSON 报告: {args.json_output}")

    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
