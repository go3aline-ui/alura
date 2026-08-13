"""Executa a matriz de perguntas reais e salva um relatório JSON."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bimbam_rag.service import RAGService  # noqa: E402
from bimbam_rag.telegram_demo import evaluate_answer, load_cases  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    service = RAGService(
        pdf_path=ROOT / "data" / "politica_reembolsos_devolucoes_bimbam_buy.pdf",
        index_path=ROOT / "data" / "vector_index.json",
    )

    results = []
    for case in load_cases(ROOT / "data" / "perguntas_teste.json"):
        answer = service.ask(case["question"])
        evaluation = evaluate_answer(case, answer)
        results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "passed": evaluation.passed,
                "answer": answer.answer,
                "grounded": answer.grounded,
                "pages": sorted({page for source in answer.sources for page in source.pages}),
                "scores": [round(source.score, 4) for source in answer.sources],
                "checks": list(evaluation.checks),
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "results": results,
    }
    output = ROOT / "reports" / "avaliacao_rag.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Avaliação: {report['passed']}/{report['total']} casos aprovados.")
    print(f"Relatório: {output}")
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()

