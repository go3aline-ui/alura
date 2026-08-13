"""Leitura, limpeza e divisão do PDF em trechos pesquisáveis."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentChunk


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_text(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_large_block(block: str, limit: int) -> list[str]:
    if len(block) <= limit:
        return [block]

    sentences = re.split(r"(?<=[.!?])\s+", block)
    parts: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > limit:
            parts.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


def _page_chunks(text: str, page_number: int, chunk_size: int, overlap: int) -> list[DocumentChunk]:
    blocks: list[str] = []
    for paragraph in re.split(r"\n\s*\n", clean_text(text)):
        paragraph = paragraph.strip()
        if paragraph:
            blocks.extend(_split_large_block(paragraph, chunk_size))

    chunks: list[DocumentChunk] = []
    current = ""
    chunk_number = 1
    for block in blocks:
        candidate = f"{current}\n\n{block}".strip()
        if current and len(candidate) > chunk_size:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"p{page_number:02d}-c{chunk_number:02d}",
                    text=current,
                    pages=(page_number,),
                )
            )
            chunk_number += 1
            tail = current[-overlap:].lstrip() if overlap else ""
            current = f"{tail}\n\n{block}".strip()
        else:
            current = candidate

    if current:
        chunks.append(
            DocumentChunk(
                chunk_id=f"p{page_number:02d}-c{chunk_number:02d}",
                text=current,
                pages=(page_number,),
            )
        )
    return chunks


def read_pdf_chunks(path: Path, chunk_size: int = 1_400, overlap: int = 220) -> list[DocumentChunk]:
    if not path.exists():
        raise FileNotFoundError(f"PDF não encontrado: {path}")
    if chunk_size < 400:
        raise ValueError("chunk_size deve ser maior ou igual a 400")
    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap deve estar entre 0 e chunk_size - 1")

    reader = PdfReader(str(path))
    chunks: list[DocumentChunk] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            chunks.extend(_page_chunks(text, page_number, chunk_size, overlap))

    if not chunks:
        raise ValueError("O PDF não possui texto pesquisável")
    return chunks

