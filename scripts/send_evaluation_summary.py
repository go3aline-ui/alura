"""Publica no grupo do Telegram o resumo dos relatórios de avaliação."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bimbam_rag.telegram_demo import coordinator_from_environment, load_cases  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    retrieval = json.loads(
        (ROOT / "reports" / "avaliacao_recuperacao.json").read_text(encoding="utf-8")
    )
    generation = json.loads(
        (ROOT / "reports" / "avaliacao_rag.json").read_text(encoding="utf-8")
    )
    matrix = load_cases(ROOT / "data" / "perguntas_teste.json")
    coordinator = coordinator_from_environment(ROOT)
    coordinator.auditor_api.send_message(
        coordinator.chat_id,
        "✅ HOMOLOGAÇÃO AMPLIADA CONCLUÍDA\n\n"
        f"Matriz: {len(matrix)} perguntas\n"
        f"Recuperação e fontes: {retrieval['passed']}/{retrieval['total']} aprovadas\n"
        f"Respostas críticas ponta a ponta: {generation['passed']}/{generation['total']} aprovadas\n\n"
        "Inclui paráfrases, ambiguidade, premissas falsas, perguntas fora do PDF "
        "e tentativa de injeção de prompt.",
    )
    print("Resumo de avaliação enviado pelo Bot Auditor.")


if __name__ == "__main__":
    main()
