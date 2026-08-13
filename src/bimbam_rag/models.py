"""Modelos de dados usados pelo pipeline RAG."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    text: str
    pages: tuple[int, ...]


@dataclass(frozen=True)
class SearchResult:
    chunk: DocumentChunk
    score: float


@dataclass(frozen=True)
class SourceExcerpt:
    chunk_id: str
    pages: tuple[int, ...]
    score: float
    text: str


@dataclass(frozen=True)
class RAGAnswer:
    question: str
    answer: str
    sources: tuple[SourceExcerpt, ...]
    grounded: bool

    def to_dict(self) -> dict:
        return asdict(self)

