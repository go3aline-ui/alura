"""Base vetorial local e pequena, adequada ao documento do Challenge."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .models import DocumentChunk, SearchResult


INDEX_VERSION = 2


def normalize_vector(values: list[float] | np.ndarray) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm == 0:
        raise ValueError("Embedding inválido ou vazio")
    return vector / norm


@dataclass
class VectorStore:
    chunks: list[DocumentChunk]
    vectors: np.ndarray
    document_hash: str
    embedding_model: str

    def __post_init__(self) -> None:
        if len(self.chunks) != len(self.vectors):
            raise ValueError("A quantidade de chunks e embeddings não coincide")
        if self.vectors.ndim != 2:
            raise ValueError("Os embeddings devem formar uma matriz")

    @classmethod
    def from_embeddings(
        cls,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
        document_hash: str,
        embedding_model: str,
    ) -> "VectorStore":
        vectors = np.vstack([normalize_vector(values) for values in embeddings])
        return cls(chunks, vectors, document_hash, embedding_model)

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[SearchResult]:
        if top_k < 1:
            raise ValueError("top_k deve ser positivo")
        query = normalize_vector(query_embedding)
        if query.shape[0] != self.vectors.shape[1]:
            raise ValueError("A dimensão da pergunta difere da base vetorial")

        scores = self.vectors @ query
        order = np.argsort(scores)[::-1][: min(top_k, len(scores))]
        return [
            SearchResult(chunk=self.chunks[int(index)], score=float(scores[int(index)]))
            for index in order
        ]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": INDEX_VERSION,
            "document_hash": self.document_hash,
            "embedding_model": self.embedding_model,
            "dimensions": int(self.vectors.shape[1]),
            "items": [
                {
                    "chunk_id": chunk.chunk_id,
                    "document_name": chunk.document_name,
                    "pages": list(chunk.pages),
                    "text": chunk.text,
                    "vector": self.vectors[index].tolist(),
                }
                for index, chunk in enumerate(self.chunks)
            ],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def load(cls, path: Path) -> "VectorStore":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != INDEX_VERSION:
            raise ValueError("Versão da base vetorial incompatível")
        chunks = [
            DocumentChunk(
                chunk_id=item["chunk_id"],
                pages=tuple(int(page) for page in item["pages"]),
                text=item["text"],
                document_name=item.get("document_name", ""),
            )
            for item in payload["items"]
        ]
        vectors = np.asarray([item["vector"] for item in payload["items"]], dtype=np.float32)
        return cls(
            chunks=chunks,
            vectors=vectors,
            document_hash=payload["document_hash"],
            embedding_model=payload["embedding_model"],
        )
