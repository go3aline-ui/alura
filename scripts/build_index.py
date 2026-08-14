"""Cria ou atualiza a base vetorial do documento."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bimbam_rag.library import list_pdf_paths  # noqa: E402
from bimbam_rag.service import RAGService  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    service = RAGService(
        pdf_paths=list_pdf_paths(ROOT / "data"),
        index_path=ROOT / "data" / "vector_index.json",
    )
    store = service.ensure_index(force=True)
    print(
        f"Base vetorial criada: {len(store.chunks)} trechos, "
        f"{store.vectors.shape[1]} dimensões, modelo {store.embedding_model}."
    )


if __name__ == "__main__":
    main()
