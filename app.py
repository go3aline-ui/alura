"""Interface web do agente documental BimBam Buy."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from bimbam_rag.library import (  # noqa: E402
    DuplicatePDFError,
    PDFDocument,
    PDFLibraryError,
    add_pdf,
    delete_pdf,
    list_pdf_documents,
    list_pdf_paths,
)
from bimbam_rag.service import ConfigurationError, RAGService  # noqa: E402


DATA_DIR = ROOT / "data"
INDEX_PATH = DATA_DIR / "vector_index.json"


st.set_page_config(
    page_title="Agente BimBam Buy",
    page_icon="🔎",
    layout="centered",
)

st.markdown(
    """
    <style>
      .block-container, [data-testid="stMainBlockContainer"] {
        max-width: 760px !important;
        padding-top: 2rem;
      }
      [data-testid="stChatMessageContent"] {
        max-width: 500px;
        overflow-wrap: anywhere;
      }
      .hero {
        padding: 1.35rem 1.5rem;
        border: 1px solid #ddd4ff;
        border-radius: 18px;
        background: linear-gradient(135deg, #f6f2ff 0%, #ffffff 75%);
        margin-bottom: 1.2rem;
      }
      .hero h1 {margin: 0 0 .35rem 0; font-size: 2rem;}
      .hero p {margin: 0; color: #584b6c;}
      .trust-note {
        font-size: .9rem;
        color: #584b6c;
        padding: .8rem 1rem;
        background: #f0ecff;
        border-radius: 12px;
      }
      .document-meta {color: #6a6075; font-size: .86rem;}
    </style>
    <div class="hero">
      <h1>🔎 Agente BimBam Buy</h1>
      <p>Consulte a biblioteca corporativa com respostas baseadas exclusivamente nos documentos.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

load_dotenv(ROOT / ".env")


@st.cache_resource
def get_service(document_paths: tuple[str, ...]) -> RAGService:
    return RAGService(
        pdf_paths=[Path(path) for path in document_paths],
        index_path=INDEX_PATH,
        top_k=int(os.getenv("TOP_K", "4")),
        min_similarity=float(os.getenv("MIN_SIMILARITY", "0.35")),
    )


def clear_document_cache() -> None:
    get_service.clear()
    st.session_state.messages = []


def set_flash(kind: str, message: str) -> None:
    st.session_state.document_flash = {"kind": kind, "message": message}


def show_flash() -> None:
    flash = st.session_state.pop("document_flash", None)
    if not flash:
        return
    renderer = st.success if flash["kind"] == "success" else st.warning
    renderer(flash["message"])


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    document_count = len({source["document_name"] for source in sources})
    label = f"{len(sources)} trecho(s) consultado(s) em {document_count} documento(s)"
    with st.expander(label):
        for source in sources:
            source_pages = ", ".join(str(page) for page in source["pages"])
            st.caption(
                f"{source['document_name']} · página(s) {source_pages} · "
                f"similaridade {source['score']:.1%}"
            )
            st.write(source["text"])
            st.divider()


@st.dialog("Excluir documento?")
def confirm_delete(document: PDFDocument) -> None:
    st.warning(
        f"O documento **{document.title}** será removido da biblioteca e deixará de ser usado nas respostas."
    )
    left, right = st.columns(2)
    with left:
        if st.button("Cancelar", use_container_width=True):
            st.rerun()
    with right:
        if st.button("🗑️ Excluir", type="primary", use_container_width=True):
            try:
                title = delete_pdf(DATA_DIR, document.path)
                clear_document_cache()
                set_flash("success", f"{title} foi removido da biblioteca.")
                st.rerun()
            except PDFLibraryError as exc:
                st.error(str(exc))


show_flash()
documents = list_pdf_documents(DATA_DIR)

with st.expander(f"📚 Biblioteca de documentos · {len(documents)} PDF(s)", expanded=False):
    st.write(
        "Adicione novos PDFs pesquisáveis ou gerencie os documentos que o agente já consulta. "
        "O arquivo atual só será apagado se você confirmar na lixeira."
    )
    uploaded_files = st.file_uploader(
        "Adicionar mais PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="Cada PDF pode ter até 25 MB e precisa conter texto pesquisável.",
    )
    if st.button(
        "Adicionar à biblioteca",
        disabled=not uploaded_files,
        type="primary",
        use_container_width=True,
    ):
        added: list[str] = []
        warnings: list[str] = []
        for uploaded_file in uploaded_files or []:
            try:
                document = add_pdf(DATA_DIR, uploaded_file.name, uploaded_file.getvalue())
                added.append(document.title)
            except (DuplicatePDFError, PDFLibraryError) as exc:
                warnings.append(f"{uploaded_file.name}: {exc}")
        if added:
            clear_document_cache()
            set_flash("success", f"{len(added)} PDF(s) adicionado(s) à biblioteca.")
        if warnings:
            st.session_state.upload_warnings = warnings
        st.rerun()

    for warning in st.session_state.pop("upload_warnings", []):
        st.warning(warning)

    st.divider()
    for document in documents:
        info, download, remove = st.columns([5.2, 1.4, 0.8], vertical_alignment="center")
        with info:
            st.markdown(f"**{document.title}**")
            st.caption(
                f"{document.pages} página(s) · {document.size_bytes / 1024:.0f} KB · {document.path.name}"
            )
        with download:
            st.download_button(
                "Baixar",
                data=document.path.read_bytes(),
                file_name=document.path.name,
                mime="application/pdf",
                key=f"download-{document.path.name}",
                use_container_width=True,
            )
        with remove:
            if st.button(
                "🗑️",
                key=f"delete-{document.path.name}",
                help=f"Excluir {document.title}",
                disabled=len(documents) <= 1,
                use_container_width=True,
            ):
                confirm_delete(document)

if not documents:
    st.error("A biblioteca está vazia. Adicione pelo menos um PDF para usar o agente.")
    st.stop()

st.markdown(
    '<div class="trust-note">🛡️ Se a informação não estiver na biblioteca, o agente informa que não encontrou a resposta.</div>',
    unsafe_allow_html=True,
)

example_questions = (
    "Qual é o prazo para devolver um produto por arrependimento?",
    "Em quanto tempo um pedido com envio padrão costuma chegar?",
    "Quais falhas não são cobertas pela garantia?",
    "Quanto tempo um reembolso no cartão pode levar?",
    "Quando uma comissão de afiliado pode ser revertida?",
)
selected_option = st.selectbox(
    "Experimente uma pergunta:",
    options=example_questions,
    index=None,
    placeholder="Selecione uma pergunta de exemplo",
)
selected_example = selected_option if st.button(
    "Perguntar ao agente",
    disabled=selected_option is None,
    use_container_width=True,
) else None

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(message.get("sources", []))

typed_question = st.chat_input("Escreva sua pergunta sobre os documentos da BimBam Buy")
question = typed_question or selected_example

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Consultando a biblioteca da BimBam Buy..."):
            try:
                paths = tuple(str(path) for path in list_pdf_paths(DATA_DIR))
                result = get_service(paths).ask(question)
                sources = [
                    {
                        "chunk_id": source.chunk_id,
                        "document_name": source.document_name,
                        "pages": list(source.pages),
                        "score": source.score,
                        "text": source.text,
                    }
                    for source in result.sources
                ]
                st.markdown(result.answer)
                render_sources(sources)
                st.session_state.messages.append(
                    {"role": "assistant", "content": result.answer, "sources": sources}
                )
            except ConfigurationError:
                message = "A chave do modelo ainda não foi configurada no servidor."
                st.error(message)
                st.session_state.messages.append(
                    {"role": "assistant", "content": message, "sources": []}
                )
            except Exception:
                message = "Não foi possível consultar os documentos agora. Tente novamente em instantes."
                st.error(message)
                st.session_state.messages.append(
                    {"role": "assistant", "content": message, "sources": []}
                )
