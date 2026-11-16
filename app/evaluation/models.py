from __future__ import annotations

from pydantic import BaseModel, Field


class CaseExpectation(BaseModel):
    blocked: bool
    risk_level: str | None = None
    exact_reply: str | None = None
    expect_retrieval: bool = False
    retrieval_terms_all: list[str] = Field(default_factory=list)
    expected_sources_any: list[str] = Field(default_factory=list)
    expected_top_source: str | None = None
    expected_top_authority: str | None = None
    expect_conflict: bool | None = None
    reply_terms_all: list[str] = Field(default_factory=list)
    reply_forbidden: list[str] = Field(default_factory=list)
    sources_required: bool = False
    disclaimer_required: bool = True


class EvaluationCase(BaseModel):
    id: str
    category: str
    input: str
    expect: CaseExpectation


class EvaluationResult(BaseModel):
    case_id: str
    category: str
    input: str
    passed: bool
    safety_pass: bool
    retrieval_pass: bool | None = None
    ranking_pass: bool | None = None
    authority_pass: bool | None = None
    conflict_pass: bool | None = None
    answer_pass: bool | None = None
    failures: list[str] = Field(default_factory=list)
    blocked: bool | None = None
    risk_level: str | None = None
    retrieved_sources: list[str] = Field(default_factory=list)
    top_source: str | None = None
    hit_at_k: bool | None = None
    reciprocal_rank: float | None = None
    detected_conflicts: list[str] = Field(default_factory=list)
    reply: str | None = None


class EvaluationSummary(BaseModel):
    total: int
    passed: int
    failed: int
    pass_rate: float
    safety_passed: int
    safety_total: int
    retrieval_passed: int
    retrieval_total: int
    ranking_passed: int = 0
    ranking_total: int = 0
    authority_passed: int = 0
    authority_total: int = 0
    conflict_passed: int = 0
    conflict_total: int = 0
    hit_at_k_average: float | None = None
    mrr: float | None = None
    answer_passed: int | None
    answer_total: int | None
    results: list[EvaluationResult]
