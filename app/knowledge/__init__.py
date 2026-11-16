"""Knowledge base abstractions and local markdown implementation."""

from app.knowledge.base import KnowledgeBase, RetrievedChunk
from app.knowledge.local_markdown import MarkdownKnowledgeBase

__all__ = ["KnowledgeBase", "MarkdownKnowledgeBase", "RetrievedChunk"]

