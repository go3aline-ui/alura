from pathlib import Path

from bimbam_rag.models import DocumentChunk
from bimbam_rag.vector_store import VectorStore


def test_vector_store_returns_the_most_similar_chunk(tmp_path: Path) -> None:
    chunks = [
        DocumentChunk("prazo", "Devolução em 10 dias.", (4,)),
        DocumentChunk("custo", "A empresa assume o frete quando erra.", (7,)),
    ]
    store = VectorStore.from_embeddings(
        chunks=chunks,
        embeddings=[[1.0, 0.0], [0.0, 1.0]],
        document_hash="abc",
        embedding_model="fake",
    )

    result = store.search([0.9, 0.1], top_k=1)

    assert result[0].chunk.chunk_id == "prazo"
    assert result[0].score > 0.9

    path = tmp_path / "index.json"
    store.save(path)
    loaded = VectorStore.load(path)
    assert loaded.search([0.9, 0.1], top_k=1)[0].chunk.chunk_id == "prazo"

