import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data" / "perguntas_teste.json"


def test_matrix_has_broad_and_valid_coverage() -> None:
    cases = json.loads(MATRIX.read_text(encoding="utf-8"))

    assert len(cases) >= 50
    assert len({case["id"] for case in cases}) == len(cases)
    assert sum(bool(case.get("live")) for case in cases) >= 12
    assert sum(not case["expect_grounded"] for case in cases) >= 2
    assert any("injecao_prompt" in case.get("tags", []) for case in cases)
    assert any("ambigua" in case.get("tags", []) for case in cases)

    for case in cases:
        assert case["question"].strip()
        assert case["required_groups"]
        if case["expect_grounded"]:
            assert case["expected_pages"]
            assert case["retrieval_groups"]
