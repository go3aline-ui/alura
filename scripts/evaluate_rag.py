"""Executa respostas reais do RAG e salva um relatório JSON."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bimbam_rag.library import list_pdf_paths  # noqa: E402
from bimbam_rag.service import RAGService  # noqa: E402
from bimbam_rag.telegram_demo import evaluate_answer, live_cases, load_cases  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia respostas geradas pelo RAG")
    parser.add_argument(
        "--all",
        action="store_true",
        help="gera respostas para toda a matriz; requer cota suficiente da API",
    )
    parser.add_argument("--delay", type=float, default=5.0, help="intervalo entre chamadas")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="repete somente os casos reprovados do relatório existente",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    service = RAGService(
        pdf_paths=list_pdf_paths(ROOT / "data"),
        index_path=ROOT / "data" / "vector_index.json",
    )
    matrix = load_cases(ROOT / "data" / "perguntas_teste.json")
    cases = matrix if args.all else live_cases(matrix)
    output = ROOT / "reports" / "avaliacao_rag.json"
    previous_report = None
    if args.resume:
        if not output.exists():
            raise FileNotFoundError("Não existe relatório anterior para continuar")
        previous_report = json.loads(output.read_text(encoding="utf-8"))
        failed_ids = {
            item["id"] for item in previous_report["results"] if not item["passed"]
        }
        cases = [case for case in cases if case["id"] in failed_ids]
        if not cases:
            print("O relatório existente já está totalmente aprovado.")
            return

    results = []
    for position, case in enumerate(cases):
        try:
            answer = service.ask(case["question"])
            evaluation = evaluate_answer(case, answer)
            results.append(
                {
                    "id": case["id"],
                    "category": case.get("category"),
                    "question": case["question"],
                    "passed": evaluation.passed,
                    "answer": answer.answer,
                    "grounded": answer.grounded,
                    "pages": sorted(
                        {page for source in answer.sources for page in source.pages}
                    ),
                    "scores": [round(source.score, 4) for source in answer.sources],
                    "checks": list(evaluation.checks),
                }
            )
        except Exception as error:
            results.append(
                {
                    "id": case["id"],
                    "category": case.get("category"),
                    "question": case["question"],
                    "passed": False,
                    "error": type(error).__name__,
                }
            )
        if position + 1 < len(cases) and args.delay > 0:
            time.sleep(args.delay)

    if previous_report is not None:
        replacements = {item["id"]: item for item in results}
        results = [
            replacements.get(item["id"], item) for item in previous_report["results"]
        ]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "all" if args.all else "live",
        "resumed": args.resume,
        "matrix_total": len(matrix),
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Avaliação RAG: {report['passed']}/{report['total']} casos aprovados.")
    print(f"Relatório: {output}")
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
