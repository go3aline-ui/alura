"""Interface web mínima do Agente BimBam Buy."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from bimbam_rag.service import ConfigurationError, RAGService  # noqa: E402


PDF_PATH = ROOT / "data" / "politica_reembolsos_devolucoes_bimbam_buy.pdf"
INDEX_PATH = ROOT / "data" / "vector_index.json"


st.set_page_config(
    page_title="Agente BimBam Buy",
    page_icon="🔎",
    layout="centered",
)

st.markdown(
    """
    <style>
      .block-container, [data-testid="stMainBlockContainer"] {
        max-width: 700px !important;
        padding-top: 2rem;
      }
      [data-testid="stChatMessageContent"] {
        max-width: 420px;
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
    </style>
    <div class="hero">
      <h1>🔎 Agente BimBam Buy</h1>
      <p>Tire dúvidas sobre reembolsos e devoluções com respostas baseadas no documento oficial.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

load_dotenv(ROOT / ".env")


@st.cache_resource
def get_service() -> RAGService:
    return RAGService(
        pdf_path=PDF_PATH,
        index_path=INDEX_PATH,
        top_k=int(os.getenv("TOP_K", "4")),
        min_similarity=float(os.getenv("MIN_SIMILARITY", "0.35")),
    )


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    pages = sorted({page for source in sources for page in source["pages"]})
    page_label = ", ".join(str(page) for page in pages)
    with st.expander(f"Trechos consultados - página(s) {page_label}"):
        for source in sources:
            source_pages = ", ".join(str(page) for page in source["pages"])
            st.caption(
                f"Página(s) {source_pages} · similaridade {source['score']:.1%} · {source['chunk_id']}"
            )
            st.write(source["text"])
            st.divider()


with st.expander("Sobre o agente e o documento"):
    st.write(
        "O sistema lê o PDF, divide o texto em chunks, cria embeddings, recupera os trechos "
        "mais relacionados e usa o Gemini para formular a resposta."
    )
    st.markdown("**Documento:** Política de Reembolsos e Devoluções da BimBam Buy")
    st.download_button(
        "Baixar documento usado",
        data=PDF_PATH.read_bytes(),
        file_name=PDF_PATH.name,
        mime="application/pdf",
        use_container_width=True,
    )

st.markdown(
    '<div class="trust-note">🛡️ Se a informação não estiver no PDF, o agente informa que não encontrou a resposta.</div>',
    unsafe_allow_html=True,
)

example_questions = (
    "Qual é o prazo para devolver um produto por arrependimento?",
    "Quem paga o custo da devolução quando a empresa envia o produto errado?",
    "Quanto tempo demora para receber um reembolso aprovado?",
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

typed_question = st.chat_input("Escreva sua pergunta sobre reembolsos ou devoluções")
question = typed_question or selected_example

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Consultando a política da BimBam Buy..."):
            try:
                result = get_service().ask(question)
                sources = [
                    {
                        "chunk_id": source.chunk_id,
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
                message = "Não foi possível consultar o documento agora. Tente novamente em instantes."
                st.error(message)
                st.session_state.messages.append(
                    {"role": "assistant", "content": message, "sources": []}
                )
