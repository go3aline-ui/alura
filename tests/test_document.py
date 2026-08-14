from pathlib import Path

from bimbam_rag.document import read_pdf_chunks, read_pdf_collection


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "politica_reembolsos_devolucoes_bimbam_buy.pdf"
WARRANTY_PDF = ROOT / "data" / "manual_garantia_produtos_bimbam_buy.pdf"


def test_pdf_is_split_into_page_aware_chunks() -> None:
    chunks = read_pdf_chunks(PDF)

    assert len(chunks) >= 14
    assert chunks[0].pages == (1,)
    assert all(chunk.text.strip() for chunk in chunks)
    assert any("10 dias corridos" in chunk.text for chunk in chunks)
    assert any("5 a 10 dias úteis" in chunk.text for chunk in chunks)


def test_every_chunk_stays_under_a_safe_size() -> None:
    chunks = read_pdf_chunks(PDF, chunk_size=1_400, overlap=220)

    assert max(len(chunk.text) for chunk in chunks) < 1_700


def test_pdf_collection_keeps_document_identity_and_unique_ids() -> None:
    chunks = read_pdf_collection([PDF, WARRANTY_PDF])

    document_names = {chunk.document_name for chunk in chunks}
    chunk_ids = [chunk.chunk_id for chunk in chunks]
    assert len(document_names) == 2
    assert len(chunk_ids) == len(set(chunk_ids))
    assert any("Prazos de garantia" in chunk.text for chunk in chunks)
