from pathlib import Path
from types import SimpleNamespace

from bimbam_rag.service import RAGService
from bimbam_rag.models import DocumentChunk
from bimbam_rag.vector_store import VectorStore
from bimbam_rag.document import file_sha256


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "politica_reembolsos_devolucoes_bimbam_buy.pdf"


class FakeModels:
    def embed_content(self, *, contents, **_kwargs):
        texts = contents if isinstance(contents, list) else [contents]
        embeddings = []
        for text in texts:
            normalized = text.lower()
            is_target_document = "10 dias corridos" in normalized
            is_target_query = (
                "desistir da compra" in normalized or "condições e o prazo" in normalized
            )
            values = [1.0, 0.0] if is_target_document or is_target_query else [0.0, 1.0]
            embeddings.append(SimpleNamespace(values=values))
        return SimpleNamespace(embeddings=embeddings)

    def generate_content(self, *, contents, **_kwargs):
        assert "10 dias corridos" in contents
        return SimpleNamespace(
            text="A devolução por arrependimento pode ser solicitada em até 10 dias corridos. Fonte: página 4."
        )


def test_service_retrieves_context_and_generates_grounded_answer(tmp_path: Path) -> None:
    service = RAGService(
        pdf_path=PDF,
        index_path=tmp_path / "index.json",
        client=SimpleNamespace(models=FakeModels()),
        min_similarity=0.8,
    )

    answer = service.ask("Qual é o prazo para desistir da compra?")

    assert answer.grounded is True
    assert "10 dias corridos" in answer.answer
    assert 4 in {page for source in answer.sources for page in source.pages}


def test_retrieval_includes_neighbor_when_section_crosses_pages(tmp_path: Path) -> None:
    service = RAGService(
        pdf_path=PDF,
        index_path=tmp_path / "index.json",
        client=SimpleNamespace(models=FakeModels()),
        top_k=1,
    )
    service._store = VectorStore.from_embeddings(
        chunks=[
            DocumentChunk("p04-c02", "Comprovante de compra ou número do pedido", (4,)),
            DocumentChunk("p05-c01", "Prazo, acessórios e embalagem original", (5,)),
            DocumentChunk("p05-c02", "Casos não elegíveis", (5,)),
        ],
        embeddings=[[0.99, 0.01], [1.0, 0.0], [0.0, 1.0]],
        document_hash=file_sha256(PDF),
        embedding_model=service.embedding_model,
    )

    results = service.retrieve("Quais são as condições e o prazo?")

    assert {result.chunk.chunk_id for result in results} == {
        "p04-c02",
        "p05-c01",
        "p05-c02",
    }


def test_retrieve_many_returns_one_result_group_per_question(tmp_path: Path) -> None:
    service = RAGService(
        pdf_path=PDF,
        index_path=tmp_path / "index.json",
        client=SimpleNamespace(models=FakeModels()),
    )

    results = service.retrieve_many(
        ["Qual é o prazo para desistir da compra?", "Quais são as condições e o prazo?"]
    )

    assert len(results) == 2
    assert all(result_group for result_group in results)
