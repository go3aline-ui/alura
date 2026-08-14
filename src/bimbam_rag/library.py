"""Gerenciamento seguro da biblioteca de documentos PDF."""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


MAX_PDF_SIZE = 25 * 1024 * 1024


class PDFLibraryError(ValueError):
    """Erro de validação ou operação na biblioteca de PDFs."""


class DuplicatePDFError(PDFLibraryError):
    """O conteúdo enviado já existe na biblioteca."""


@dataclass(frozen=True)
class PDFDocument:
    path: Path
    title: str
    pages: int
    size_bytes: int


def _content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _path_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _title_from_reader(reader: PdfReader, fallback: str) -> str:
    text = reader.pages[0].extract_text() or ""
    heading: list[str] = []
    for line in text.splitlines():
        line = " ".join(line.split()).strip()
        if not line:
            continue
        if line.casefold() in {"índice", "indice", "sumário", "sumario"}:
            break
        heading.append(line)
        if len(" ".join(heading)) >= 100:
            break
    return " ".join(heading).strip() or fallback


def validate_pdf_content(content: bytes, filename: str = "documento.pdf") -> tuple[int, str]:
    if not filename.lower().endswith(".pdf"):
        raise PDFLibraryError("Envie somente arquivos com extensão PDF.")
    if not content:
        raise PDFLibraryError("O arquivo está vazio.")
    if len(content) > MAX_PDF_SIZE:
        raise PDFLibraryError("O PDF deve ter no máximo 25 MB.")
    if not content.lstrip().startswith(b"%PDF-"):
        raise PDFLibraryError("O arquivo não possui uma estrutura PDF válida.")

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise PDFLibraryError("PDFs protegidos por senha não são aceitos.")
        if not reader.pages:
            raise PDFLibraryError("O PDF não possui páginas.")
        searchable = any((page.extract_text() or "").strip() for page in reader.pages)
        if not searchable:
            raise PDFLibraryError("O PDF não possui texto pesquisável.")
        title = _title_from_reader(reader, Path(filename).stem)
        return len(reader.pages), title
    except PDFLibraryError:
        raise
    except Exception as exc:
        raise PDFLibraryError("Não foi possível ler este PDF.") from exc


def _safe_filename(filename: str) -> str:
    stem = Path(filename).stem
    normalized = unicodedata.normalize("NFKD", stem)
    ascii_stem = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_stem = re.sub(r"[^a-z0-9]+", "_", ascii_stem).strip("_")
    return f"{ascii_stem[:100] or 'documento'}.pdf"


def list_pdf_paths(data_dir: Path) -> tuple[Path, ...]:
    data_dir = data_dir.resolve()
    documents_dir = (data_dir / "documents").resolve()
    candidates = list(data_dir.glob("*.pdf"))
    if documents_dir.exists():
        candidates.extend(documents_dir.glob("*.pdf"))
    unique = {path.resolve() for path in candidates if path.is_file()}
    return tuple(sorted(unique, key=lambda path: (path.parent != data_dir, path.name.casefold())))


def describe_pdf(path: Path) -> PDFDocument:
    content = path.read_bytes()
    pages, title = validate_pdf_content(content, path.name)
    return PDFDocument(path=path.resolve(), title=title, pages=pages, size_bytes=len(content))


def list_pdf_documents(data_dir: Path) -> tuple[PDFDocument, ...]:
    return tuple(describe_pdf(path) for path in list_pdf_paths(data_dir))


def add_pdf(data_dir: Path, filename: str, content: bytes) -> PDFDocument:
    pages, title = validate_pdf_content(content, filename)
    incoming_hash = _content_sha256(content)
    for existing in list_pdf_paths(data_dir):
        if _path_sha256(existing) == incoming_hash:
            raise DuplicatePDFError(f"{existing.name} já está na biblioteca.")

    documents_dir = data_dir.resolve() / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    target = documents_dir / safe_name
    counter = 2
    while target.exists():
        target = documents_dir / f"{Path(safe_name).stem}_{counter}.pdf"
        counter += 1

    temporary = documents_dir / f".{target.name}.{uuid.uuid4().hex}.upload"
    try:
        temporary.write_bytes(content)
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()

    return PDFDocument(path=target.resolve(), title=title, pages=pages, size_bytes=len(content))


def delete_pdf(data_dir: Path, path: Path) -> str:
    data_dir = data_dir.resolve()
    documents_dir = (data_dir / "documents").resolve()
    target = path.resolve()
    if target.parent not in {data_dir, documents_dir} or target.suffix.lower() != ".pdf":
        raise PDFLibraryError("Documento fora da biblioteca.")
    if target not in list_pdf_paths(data_dir):
        raise PDFLibraryError("O documento não existe mais.")
    if len(list_pdf_paths(data_dir)) <= 1:
        raise PDFLibraryError("Mantenha pelo menos um PDF para o agente funcionar.")
    title = describe_pdf(target).title
    target.unlink()
    return title
