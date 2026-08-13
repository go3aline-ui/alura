from pathlib import Path

from bimbam_rag.document import read_pdf_chunks


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "politica_reembolsos_devolucoes_bimbam_buy.pdf"


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

