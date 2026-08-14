"""Avalia em lote a recuperação sem consumir cota de geração de texto."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bimbam_rag.library import list_pdf_paths  # noqa: E402
from bimbam_rag.service import RAGService  # noqa: E402
from bimbam_rag.telegram_demo import load_cases, normalize_text  # noqa: E402


def main() -> None:
    load_dotenv(ROOT / ".env")
    matrix = load_cases(ROOT / "data" / "perguntas_teste.json")
    cases = [case for case in matrix if case.get("expect_grounded", True)]
    service = RAGService(
        pdf_paths=list_pdf_paths(ROOT / "data"),
        index_path=ROOT / "data" / "vector_index.json",
    )

    batches = service.retrieve_many([str(case["question"]) for case in cases])
    results = []
    for case, retrieved in zip(cases, batches, strict=True):
        relevant = [item for item in retrieved if item.score >= service.min_similarity]
        text = normalize_text(" ".join(item.chunk.text for item in relevant))
        pages = {page for item in relevant for page in item.chunk.pages}
        group_checks = []
        for group in case.get("retrieval_groups", []):
            alternatives = [normalize_text(str(value)) for value in group]
            group_checks.append(any(value in text for value in alternatives))
        expected_pages = {int(page) for page in case.get("expected_pages", [])}
        page_ok = bool(pages & expected_pages)
        passed = bool(relevant) and page_ok and all(group_checks)
        results.append(
            {
                "id": case["id"],
                "category": case.get("category"),
                "passed": passed,
                "pages": sorted(pages),
                "expected_pages": sorted(expected_pages),
                "content_checks": group_checks,
                "top_scores": [round(item.score, 4) for item in relevant[:4]],
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_total": len(matrix),
        "evaluated": len(results),
        "outside_document_reserved_for_live_test": len(matrix) - len(results),
        "passed": sum(item["passed"] for item in results),
        "total": len(results),
        "results": results,
    }
    output = ROOT / "reports" / "avaliacao_recuperacao.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Recuperação: {report['passed']}/{report['total']} casos aprovados.")
    print(f"Relatório: {output}")
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
