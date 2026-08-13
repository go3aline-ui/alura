from pathlib import Path
from types import SimpleNamespace

from bimbam_rag.service import RAGService


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "politica_reembolsos_devolucoes_bimbam_buy.pdf"


class FakeModels:
    def embed_content(self, *, contents, **_kwargs):
        texts = contents if isinstance(contents, list) else [contents]
        embeddings = []
        for text in texts:
            normalized = text.lower()
            is_target_document = "10 dias corridos" in normalized
            is_target_query = "desistir da compra" in normalized
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
