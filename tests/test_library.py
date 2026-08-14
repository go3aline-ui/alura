from pathlib import Path

import pytest

from bimbam_rag.library import (
    DuplicatePDFError,
    PDFLibraryError,
    add_pdf,
    delete_pdf,
    list_pdf_documents,
)


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data" / "politica_reembolsos_devolucoes_bimbam_buy.pdf"
WARRANTY = ROOT / "data" / "manual_garantia_produtos_bimbam_buy.pdf"


def test_add_list_duplicate_and_delete_pdfs(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    first = add_pdf(data_dir, "politica.pdf", POLICY.read_bytes())
    assert first.path.exists()
    assert len(list_pdf_documents(data_dir)) == 1

    with pytest.raises(DuplicatePDFError):
        add_pdf(data_dir, "copia.pdf", POLICY.read_bytes())

    second = add_pdf(data_dir, "garantia.pdf", WARRANTY.read_bytes())
    assert len(list_pdf_documents(data_dir)) == 2
    delete_pdf(data_dir, second.path)
    assert len(list_pdf_documents(data_dir)) == 1

    with pytest.raises(PDFLibraryError, match="pelo menos um PDF"):
        delete_pdf(data_dir, first.path)


def test_rejects_non_pdf_content(tmp_path: Path) -> None:
    with pytest.raises(PDFLibraryError, match="estrutura PDF"):
        add_pdf(tmp_path / "data", "arquivo.pdf", b"nao e pdf")
