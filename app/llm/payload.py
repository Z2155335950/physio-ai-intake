from __future__ import annotations

from app.knowledge.base import RetrievedChunk


def format_knowledge_context(knowledge: list[RetrievedChunk]) -> str:
    if not knowledge:
        return "（本次没有检索到门店知识库内容）"
    return "\n\n".join(
        f"[资料{i}｜{item.authority_label}（{item.authority_level}）"
        f"｜{item.source}｜{item.title}｜重排分 {item.rerank_score:.4f}]\n"
        f"{item.content}"
        for i, item in enumerate(knowledge, start=1)
    )


def build_model_system_content(
    system_prompt: str, knowledge: list[RetrievedChunk]
) -> str:
    return (
        f"{system_prompt}\n\n"
        "以下是本次检索到的门店知识，只可基于这些内容回答：\n"
        f"<knowledge>\n{format_knowledge_context(knowledge)}\n</knowledge>"
    )
