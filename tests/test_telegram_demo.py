from types import SimpleNamespace

from bimbam_rag.models import RAGAnswer, SourceExcerpt
from bimbam_rag.telegram_demo import TelegramDemoCoordinator, evaluate_answer


class FakeAPI:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send_message(self, chat_id: str, text: str) -> dict:
        self.messages.append((chat_id, text))
        return {"message_id": len(self.messages)}


def grounded_answer() -> RAGAnswer:
    return RAGAnswer(
        question="Qual é o prazo?",
        answer="O prazo é de 10 dias corridos. Fonte: página 4.",
        sources=(SourceExcerpt("p04-c01", (4,), 0.91, "prazo de 10 dias corridos"),),
        grounded=True,
    )


def test_evaluator_checks_content_grounding_and_page() -> None:
    case = {
        "id": "prazo",
        "required_groups": [["10 dias corridos"]],
        "expected_pages": [4],
        "expect_grounded": True,
    }

    evaluation = evaluate_answer(case, grounded_answer())

    assert evaluation.passed is True
    assert len(evaluation.checks) == 3


def test_coordinator_uses_both_bots_and_posts_verdict() -> None:
    auditor = FakeAPI()
    attendant = FakeAPI()
    service = SimpleNamespace(ask=lambda _question: grounded_answer())
    case = {
        "id": "prazo",
        "question": "Qual é o prazo?",
        "required_groups": [["10 dias corridos"]],
        "expected_pages": [4],
        "expect_grounded": True,
    }
    coordinator = TelegramDemoCoordinator(
        service=service,
        auditor_api=auditor,
        attendant_api=attendant,
        chat_id="-100123",
        test_cases=[case],
    )

    evaluation = coordinator.run_case(case)

    assert evaluation.passed is True
    assert "BOT CLIENTE / AUDITOR" in auditor.messages[0][1]
    assert "BOT ATENDENTE RAG" in attendant.messages[0][1]
    assert "APROVADO" in auditor.messages[1][1]

