from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class SourceAuthority(BaseModel):
    authority_level: str = Field(pattern=r"^[A-D]$")
    authority_rank: int = Field(ge=0, le=100)
    source_type: str
    label: str
    owner: str = ""


class SourcePolicyEntry(SourceAuthority):
    path: str


class KnowledgePolicyDocument(BaseModel):
    version: str
    updated_at: str
    default: SourceAuthority
    sources: list[SourcePolicyEntry]

    @model_validator(mode="after")
    def ensure_unique_paths(self):
        paths = [item.path for item in self.sources]
        if len(paths) != len(set(paths)):
            raise ValueError("知识来源策略中存在重复路径")
        return self


class KnowledgePolicy:
    def __init__(self, document: KnowledgePolicyDocument) -> None:
        self._document = document
        self._sources = {item.path: item for item in document.sources}

    @classmethod
    def load(cls, path: Path | None) -> "KnowledgePolicy":
        if path is None:
            return cls.default()
        if not path.exists():
            raise FileNotFoundError(f"知识来源策略文件不存在: {path}")
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        return cls(KnowledgePolicyDocument.model_validate(payload))

    @classmethod
    def default(cls) -> "KnowledgePolicy":
        authority = SourceAuthority(
            authority_level="D",
            authority_rank=30,
            source_type="unclassified",
            label="未分级来源",
            owner="未标注",
        )
        return cls(
            KnowledgePolicyDocument(
                version="default",
                updated_at="",
                default=authority,
                sources=[],
            )
        )

    def resolve(self, source: str) -> SourceAuthority:
        return self._sources.get(source, self._document.default)

    @property
    def version(self) -> str:
        return self._document.version

