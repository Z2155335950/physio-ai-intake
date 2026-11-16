from __future__ import annotations

import uuid

from app.agent.prompt_builder import PromptBuilder
from app.agent.safety import DISCLAIMER, REDLINE_REPLY, SafetyGuard
from app.domain import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    KnowledgeConflictInfo,
    MemoryReference,
    ModelPayloadPreview,
    RiskAssessment,
    Source,
)
from app.knowledge.base import KnowledgeBase, KnowledgeSearchResult
from app.llm.base import LLMError, LLMProvider
from app.llm.demo import DemoProvider
from app.llm.payload import build_model_system_content
from app.memory.base import CustomerMemoryStore
from app.memory.models import CustomerMemoryContext
from app.sessions.base import SessionStore
from app.tools.audit import InMemoryToolAuditStore
from app.tools.base import ToolContext
from app.tools.executor import ToolExecutor
from app.tools.factory import DEFAULT_LOCAL_SCOPES, build_tool_executor


GREETING_REPLY = (
    "您好，我是理疗养护辅助助手。可以为您检索门店知识、整理评估思路、"
    "风险提醒和沟通话术。请描述您需要处理的场景。"
)


def build_high_risk_reply(risk: RiskAssessment) -> str:
    labels = "、".join(risk.labels) or "高风险信号"
    actions = "\n".join(f"- {action}" for action in risk.actions)
    return (
        f"【风险提醒】当前描述涉及{labels}。\n\n"
        f"{actions}\n\n"
        "本次不提供正骨、复位、扳法或具体调理方案。请理疗师先建议顾客前往"
        "正规医院排查，取得检查结果后再结合现场情况判断。"
    )


class AgentOrchestrator:
    def __init__(
        self,
        *,
        settings,
        knowledge_base: KnowledgeBase,
        llm: LLMProvider,
        session_store: SessionStore,
        customer_memory: CustomerMemoryStore | None = None,
        tool_executor: ToolExecutor | None = None,
        fallback_llm: LLMProvider | None = None,
        safety_guard: SafetyGuard | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self._settings = settings
        self._knowledge_base = knowledge_base
        self._llm = llm
        self._session_store = session_store
        self._customer_memory = customer_memory
        self._tool_executor = tool_executor or build_tool_executor(
            knowledge_base=knowledge_base,
            customer_memory=customer_memory,
            audit_store=InMemoryToolAuditStore(),
        )
        self._fallback_llm = fallback_llm or DemoProvider()
        self._safety_guard = safety_guard or SafetyGuard()
        self._prompt_builder = prompt_builder or PromptBuilder(
            settings.system_prompt_file
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        message_text = request.message.strip()
        session_id = request.session_id or str(uuid.uuid4())
        decision = self._safety_guard.inspect_input(message_text)
        tool_context = ToolContext(
            trace_id=session_id,
            actor_id=self._settings.tool_actor_id,
            scopes=DEFAULT_LOCAL_SCOPES,
            customer_id=request.customer_id,
            risk_level=decision.risk.level,
        )
        if request.customer_id:
            await self._tool_executor.execute(
                "get_customer_profile", {}, tool_context
            )
        await self._session_store.bind_customer(session_id, request.customer_id)

        if decision.blocked:
            await self._session_store.append(
                session_id,
                ChatMessage(role="user", content=message_text),
                ChatMessage(role="assistant", content=REDLINE_REPLY),
            )
            return ChatResponse(
                session_id=session_id,
                reply=REDLINE_REPLY,
                blocked=True,
                customer_id=request.customer_id,
                warnings=[
                    f"已触发安全拦截：{decision.redline_label or '安全红线'}"
                ],
            )

        customer_context = await self._load_customer_context(
            request.customer_id, message_text, tool_context
        )
        memory_hits = self._memory_references(customer_context)

        if self._is_simple_greeting(message_text):
            if customer_context:
                reply = (
                    f"您好，已加载客户「{customer_context.customer.name}」的纵向记忆，"
                    f"当前载入 {len(customer_context.records)} 条相关接诊记录。"
                    "请描述本次需要整理的内容。"
                    f"\n\n{DISCLAIMER}"
                )
            else:
                reply = f"{GREETING_REPLY}\n\n{DISCLAIMER}"
            await self._session_store.append(
                session_id,
                ChatMessage(role="user", content=message_text),
                ChatMessage(role="assistant", content=reply),
            )
            return ChatResponse(
                session_id=session_id,
                reply=reply,
                customer_id=request.customer_id,
                memory_used=bool(customer_context and customer_context.records),
                memory_hits=memory_hits,
            )

        if decision.risk.level == "high":
            reply = f"{build_high_risk_reply(decision.risk)}\n\n{DISCLAIMER}"
            await self._session_store.append(
                session_id,
                ChatMessage(role="user", content=message_text),
                ChatMessage(role="assistant", content=reply),
            )
            return ChatResponse(
                session_id=session_id,
                reply=reply,
                risk=decision.risk,
                customer_id=request.customer_id,
                memory_used=False,
                memory_hits=[],
            )

        knowledge_result = await self._tool_executor.execute(
            "search_store_knowledge",
            {
                "query": message_text,
                "limit": self._settings.knowledge_top_k,
            },
            tool_context,
        )
        if not isinstance(knowledge_result.data, KnowledgeSearchResult):
            raise RuntimeError("知识检索工具返回了无法识别的结果")
        retrieved = knowledge_result.data.chunks
        knowledge_conflicts = knowledge_result.data.conflicts
        if not retrieved and customer_context is None:
            reply = f"该内容不在门店知识库范围内，无法提供参考。\n\n{DISCLAIMER}"
            await self._session_store.append(
                session_id,
                ChatMessage(role="user", content=message_text),
                ChatMessage(role="assistant", content=reply),
            )
            return ChatResponse(
                session_id=session_id,
                reply=reply,
                risk=decision.risk,
                customer_id=request.customer_id,
            )

        prior_messages = await self._session_store.get(session_id)
        max_history = self._settings.max_history_messages
        history = prior_messages[-max_history:]
        current_turn = ChatMessage(role="user", content=message_text)

        rendered_memory = None
        if customer_context:
            rendered_memory, _pii_redactions = (
                customer_context.render_for_prompt(
                    include_pii=self._settings.llm_send_pii
                )
            )
        system_prompt, history = self._prompt_builder.build(
            history,
            decision.risk,
            customer_memory=rendered_memory,
            knowledge_conflicts=knowledge_conflicts,
        )
        degraded = False
        degraded_reason: str | None = None
        try:
            model_reply = await self._llm.generate(
                system_prompt=system_prompt,
                messages=[*history, current_turn],
                knowledge=retrieved,
                customer_memory=rendered_memory,
            )
        except LLMError as exc:
            degraded = True
            degraded_reason = str(exc)
            model_reply = await self._fallback_llm.generate(
                system_prompt=system_prompt,
                messages=[*history, current_turn],
                knowledge=retrieved,
                customer_memory=rendered_memory,
            )

        safe_reply, warnings = self._safety_guard.enforce_output(
            model_reply, decision.risk
        )
        if degraded:
            warnings.insert(
                0,
                "在线模型暂不可用，本次已使用本地知识检索摘要继续回答。"
                "客户档案、接诊记录和风险查询不受影响。",
            )
        if knowledge_conflicts:
            warnings.append(
                f"检索发现 {len(knowledge_conflicts)} 组来源冲突，"
                "已按权威等级和更保守表述处理。"
            )

        await self._session_store.append(
            session_id,
            current_turn,
            ChatMessage(role="assistant", content=safe_reply),
        )
        sources = [
            Source(
                index=index,
                title=item.title,
                source=item.source,
                excerpt=self._excerpt(item.content),
                score=item.score,
                authority_level=item.authority_level,
                authority_rank=item.authority_rank,
                authority_label=item.authority_label,
                source_type=item.source_type,
                retrieval_score=item.retrieval_score,
                rerank_score=item.rerank_score,
            )
            for index, item in enumerate(retrieved, start=1)
        ]
        return ChatResponse(
            session_id=session_id,
            reply=safe_reply,
            risk=decision.risk,
            sources=sources,
            customer_id=request.customer_id,
            memory_used=bool(customer_context and customer_context.records),
            memory_hits=memory_hits,
            knowledge_conflicts=[
                KnowledgeConflictInfo(
                    topic=conflict.topic,
                    preferred_source=conflict.preferred_source,
                    preferred_authority=conflict.preferred_authority,
                    involved_sources=list(conflict.involved_sources),
                    resolution=conflict.resolution,
                    conditional=conflict.conditional,
                )
                for conflict in knowledge_conflicts
            ],
            degraded=degraded,
            degraded_reason=degraded_reason,
            warnings=warnings,
        )

    async def get_session(self, session_id: str) -> list[ChatMessage]:
        return await self._session_store.get(session_id)

    async def preview_model_payload(
        self, request: ChatRequest
    ) -> ModelPayloadPreview:
        message_text = request.message.strip()
        decision = self._safety_guard.inspect_input(message_text)
        provider_name = self._llm.name
        base = {
            "provider": provider_name,
            "model": self._settings.llm_model or "demo",
            "send_pii": self._settings.llm_send_pii,
        }
        if decision.blocked:
            return ModelPayloadPreview(
                **base,
                blocked=True,
                blocked_reason=(
                    decision.redline_label or "命中安全红线，本次不会发送给模型"
                ),
                would_call_model=False,
            )
        provider_unavailable_reason: str | None = None
        if (
            self._settings.llm_provider != "demo"
            and not self._settings.llm_configured
        ):
            provider_unavailable_reason = "尚未配置 DeepSeek API Key，本次不会发送到外网"
        elif hasattr(self._llm, "status"):
            circuit = self._llm.status()
            if circuit.get("circuit_open"):
                provider_unavailable_reason = (
                    "在线模型熔断中，本次将使用本地备用而不发送到外网"
                )

        tool_context = ToolContext(
            trace_id=request.session_id or f"preview-{uuid.uuid4()}",
            actor_id=self._settings.tool_actor_id,
            scopes=DEFAULT_LOCAL_SCOPES,
            customer_id=request.customer_id,
            risk_level=decision.risk.level,
        )
        if request.customer_id:
            await self._tool_executor.execute(
                "get_customer_profile", {}, tool_context
            )
        customer_context = await self._load_customer_context(
            request.customer_id, message_text, tool_context
        )
        knowledge_result = await self._tool_executor.execute(
            "search_store_knowledge",
            {
                "query": message_text,
                "limit": self._settings.knowledge_top_k,
            },
            tool_context,
        )
        if not isinstance(knowledge_result.data, KnowledgeSearchResult):
            raise RuntimeError("知识检索工具返回了无法识别的结果")
        retrieved = knowledge_result.data.chunks
        conflicts = knowledge_result.data.conflicts
        if decision.risk.level == "high":
            return ModelPayloadPreview(
                **base,
                would_call_model=False,
                blocked_reason=(
                    "高风险请求由服务端直接引导医院排查，不发送给模型"
                ),
            )
        if not retrieved and customer_context is None:
            return ModelPayloadPreview(
                **base,
                would_call_model=False,
                blocked_reason="本地没有检索到相关知识或客户记忆",
            )

        rendered_memory = None
        pii_redactions: list[str] = []
        if customer_context:
            rendered_memory, pii_redactions = (
                customer_context.render_for_prompt(
                    include_pii=self._settings.llm_send_pii
                )
            )
        prior = (
            await self._session_store.get(request.session_id)
            if request.session_id
            else []
        )
        history = prior[-self._settings.max_history_messages :]
        messages = [
            *history,
            ChatMessage(role="user", content=message_text),
        ]
        system_prompt, _ = self._prompt_builder.build(
            history,
            decision.risk,
            customer_memory=rendered_memory,
            knowledge_conflicts=conflicts,
        )
        system_content = build_model_system_content(system_prompt, retrieved)
        return ModelPayloadPreview(
            **base,
            blocked=provider_unavailable_reason is not None,
            blocked_reason=provider_unavailable_reason,
            would_call_model=provider_unavailable_reason is None,
            system_content=system_content,
            messages=messages,
            knowledge_sources=[
                Source(
                    index=index,
                    title=item.title,
                    source=item.source,
                    excerpt=self._excerpt(item.content, 300),
                    score=item.score,
                    authority_level=item.authority_level,
                    authority_rank=item.authority_rank,
                    authority_label=item.authority_label,
                    source_type=item.source_type,
                    retrieval_score=item.retrieval_score,
                    rerank_score=item.rerank_score,
                )
                for index, item in enumerate(retrieved, start=1)
            ],
            customer_memory=rendered_memory,
            pii_redactions=pii_redactions,
            character_count=len(system_content)
            + sum(len(message.content) for message in messages),
            estimated_tokens=(
                len(system_content)
                + sum(len(message.content) for message in messages)
            )
            // 2,
        )

    async def delete_session(self, session_id: str) -> bool:
        return await self._session_store.delete(session_id)

    async def _load_customer_context(
        self,
        customer_id: str | None,
        query: str,
        tool_context: ToolContext,
    ) -> CustomerMemoryContext | None:
        if not customer_id:
            return None
        result = await self._tool_executor.execute(
            "get_customer_memory",
            {"query": query},
            tool_context,
        )
        if not isinstance(result.data, CustomerMemoryContext):
            raise RuntimeError("客户记忆工具返回了无法识别的结果")
        return result.data

    @staticmethod
    def _memory_references(
        context: CustomerMemoryContext | None,
    ) -> list[MemoryReference]:
        if not context:
            return []
        references: list[MemoryReference] = []
        for record in context.records:
            excerpt_parts = [
                value
                for value in (
                    record.symptom_duration,
                    record.trigger,
                    record.objective_findings,
                    record.followup_notes,
                )
                if value
            ]
            excerpt = "；".join(excerpt_parts)
            if len(excerpt) > 160:
                excerpt = f"{excerpt[:160].rstrip()}…"
            references.append(
                MemoryReference(
                    investigation_id=record.id,
                    visit_date=record.visit_date.isoformat(),
                    visit_type=record.visit_type,
                    chief_complaint=record.chief_complaint,
                    excerpt=excerpt,
                )
            )
        return references

    @staticmethod
    def _is_simple_greeting(text: str) -> bool:
        compact = text.strip(" \t\r\n，。！？!?")
        return compact.lower() in {"你好", "您好", "hi", "hello", "在吗"}

    @staticmethod
    def _excerpt(content: str, limit: int = 180) -> str:
        compact = " ".join(content.split())
        return compact if len(compact) <= limit else f"{compact[:limit].rstrip()}…"

