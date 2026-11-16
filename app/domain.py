from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class Source(BaseModel):
    index: int
    title: str
    source: str
    excerpt: str
    score: float
    authority_level: str = "D"
    authority_rank: int = 0
    authority_label: str = "未分级来源"
    source_type: str = "unclassified"
    retrieval_score: float = 0.0
    rerank_score: float = 0.0


class KnowledgeConflictInfo(BaseModel):
    topic: str
    preferred_source: str
    preferred_authority: str
    involved_sources: list[str] = Field(default_factory=list)
    resolution: str
    conditional: bool = False


class RiskAssessment(BaseModel):
    level: Literal["none", "caution", "high"] = "none"
    labels: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class MemoryReference(BaseModel):
    investigation_id: str
    visit_date: str
    visit_type: str
    chief_complaint: str
    excerpt: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=100)
    customer_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    blocked: bool = False
    risk: RiskAssessment = Field(default_factory=RiskAssessment)
    sources: list[Source] = Field(default_factory=list)
    customer_id: str | None = None
    memory_used: bool = False
    memory_hits: list[MemoryReference] = Field(default_factory=list)
    knowledge_conflicts: list[KnowledgeConflictInfo] = Field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]


class ModelPayloadPreview(BaseModel):
    provider: str
    model: str
    send_pii: bool
    blocked: bool = False
    blocked_reason: str | None = None
    would_call_model: bool = True
    system_content: str = ""
    messages: list[ChatMessage] = Field(default_factory=list)
    knowledge_sources: list[Source] = Field(default_factory=list)
    customer_memory: str | None = None
    pii_redactions: list[str] = Field(default_factory=list)
    character_count: int = 0
    estimated_tokens: int = 0


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=4, ge=1, le=8)


class KnowledgeSearchResponse(BaseModel):
    query: str
    reply: str
    sources: list[Source] = Field(default_factory=list)
    knowledge_conflicts: list[KnowledgeConflictInfo] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    llm_configured: bool
    llm_model: str = ""
    knowledge_documents: int
    knowledge_chunks: int
    customer_count: int = 0
    governed_tool_count: int = 0
    llm_circuit_open: bool = False
    llm_retry_after_seconds: int = 0

