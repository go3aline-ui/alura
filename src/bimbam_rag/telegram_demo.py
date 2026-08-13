"""Homologação visual do RAG com dois bots em um grupo do Telegram."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from .models import RAGAnswer
from .service import RAGService


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFD", value.lower())
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class Evaluation:
    passed: bool
    checks: tuple[str, ...]


def evaluate_answer(case: dict, result: RAGAnswer) -> Evaluation:
    answer = normalize_text(result.answer)
    checks: list[str] = []
    passed = True

    expected_grounded = bool(case.get("expect_grounded", True))
    grounded_ok = result.grounded is expected_grounded
    passed &= grounded_ok
    checks.append(
        ("✅" if grounded_ok else "❌")
        + (" resposta fundamentada" if expected_grounded else " recusou informação ausente")
    )

    for group in case.get("required_groups", []):
        alternatives = [normalize_text(item) for item in group]
        group_ok = any(alternative in answer for alternative in alternatives)
        passed &= group_ok
        checks.append(
            ("✅" if group_ok else "❌")
            + " conteúdo esperado: "
            + " ou ".join(group)
        )

    expected_pages = {int(page) for page in case.get("expected_pages", [])}
    if expected_grounded and expected_pages:
        source_pages = {page for source in result.sources for page in source.pages}
        page_ok = bool(source_pages & expected_pages)
        passed &= page_ok
        checks.append(
            ("✅" if page_ok else "❌")
            + f" fonte recuperada na página esperada ({sorted(expected_pages)})"
        )

    return Evaluation(bool(passed), tuple(checks))


class TelegramAPI:
    def __init__(self, token: str, session: requests.Session | None = None) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.session = session or requests.Session()

    def call(self, method: str, payload: dict | None = None, timeout: int = 40) -> Any:
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self.session.post(
                    f"{self.base_url}/{method}", data=payload or {}, timeout=timeout
                )
                response.raise_for_status()
                body = response.json()
                if not body.get("ok"):
                    raise RuntimeError(body.get("description", "Erro do Telegram"))
                return body.get("result")
            except (requests.RequestException, RuntimeError) as error:
                last_error = error
                if attempt == 3:
                    break
                time.sleep(min(2**attempt, 4))
        raise RuntimeError("Telegram temporariamente indisponível") from last_error

    def send_message(self, chat_id: str, text: str) -> dict:
        return self.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text[:4096],
                "disable_web_page_preview": "true",
            },
        )

    def get_updates(self, offset: int | None = None, timeout: int = 25) -> list[dict]:
        payload: dict[str, str | int] = {
            "timeout": timeout,
            "limit": 50,
            "allowed_updates": json.dumps(["message"]),
        }
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload, timeout=timeout + 10)


class TelegramDemoCoordinator:
    def __init__(
        self,
        service: RAGService,
        auditor_api: TelegramAPI,
        attendant_api: TelegramAPI,
        chat_id: str,
        test_cases: list[dict],
        allowed_user_id: str = "",
    ) -> None:
        self.service = service
        self.auditor_api = auditor_api
        self.attendant_api = attendant_api
        self.chat_id = str(chat_id)
        self.test_cases = test_cases
        self.allowed_user_id = str(allowed_user_id).strip()
        self._running = threading.Lock()

    def send_question(self, question: str) -> RAGAnswer:
        self.auditor_api.send_message(
            self.chat_id,
            "🧪 BOT CLIENTE / AUDITOR\n\n" + question,
        )
        result = self.service.ask(question)
        self.attendant_api.send_message(
            self.chat_id,
            "🤖 BOT ATENDENTE RAG\n\n" + result.answer,
        )
        return result

    def run_case(self, case: dict) -> Evaluation:
        result = self.send_question(str(case["question"]))
        evaluation = evaluate_answer(case, result)
        verdict = "APROVADO ✅" if evaluation.passed else "REVISAR ❌"
        self.auditor_api.send_message(
            self.chat_id,
            "📋 ANÁLISE DO BOT AUDITOR\n\n"
            f"Caso: {case['id']}\n"
            f"Resultado: {verdict}\n\n"
            + "\n".join(evaluation.checks),
        )
        return evaluation

    def run_suite(self) -> None:
        if not self._running.acquire(blocking=False):
            self.auditor_api.send_message(self.chat_id, "Já existe uma demonstração em execução.")
            return
        try:
            self.auditor_api.send_message(
                self.chat_id,
                f"🚀 Iniciando demonstração com {len(self.test_cases)} perguntas.",
            )
            passed = 0
            for case in self.test_cases:
                evaluation = self.run_case(case)
                passed += int(evaluation.passed)
                time.sleep(1.2)
            status = "TODOS APROVADOS ✅" if passed == len(self.test_cases) else "HÁ CASOS PARA REVISAR ⚠️"
            self.auditor_api.send_message(
                self.chat_id,
                f"🏁 Demonstração concluída\n\n{passed}/{len(self.test_cases)} casos aprovados.\n{status}",
            )
        except Exception as error:
            self.auditor_api.send_message(
                self.chat_id,
                "A demonstração foi interrompida com segurança. "
                f"Motivo: {type(error).__name__}.",
            )
        finally:
            self._running.release()

    def _authorized(self, message: dict) -> bool:
        if str((message.get("chat") or {}).get("id")) != self.chat_id:
            return False
        sender = message.get("from") or {}
        if sender.get("is_bot"):
            return False
        return not self.allowed_user_id or str(sender.get("id")) == self.allowed_user_id

    def handle_message(self, message: dict) -> None:
        if not self._authorized(message):
            return
        text = str(message.get("text") or "").strip()
        command = text.split(maxsplit=1)[0].split("@", 1)[0].lower()
        argument = text.split(maxsplit=1)[1].strip() if " " in text else ""

        if command in {"/start", "/ajuda"}:
            self.auditor_api.send_message(
                self.chat_id,
                "Comandos disponíveis:\n"
                "/demo - executa todas as perguntas de homologação\n"
                "/pergunta texto - envia uma pergunta livre ao agente\n"
                "/status - verifica se os dois bots estão ativos",
            )
        elif command == "/status":
            self.auditor_api.send_message(
                self.chat_id,
                "✅ Bot Cliente/Auditor ativo\n✅ Bot Atendente RAG configurado",
            )
        elif command == "/demo":
            threading.Thread(target=self.run_suite, daemon=True).start()
        elif command == "/pergunta":
            if not argument:
                self.auditor_api.send_message(
                    self.chat_id, "Use: /pergunta Qual é o prazo de devolução?"
                )
                return
            threading.Thread(target=self.send_question, args=(argument,), daemon=True).start()

    def poll_forever(self) -> None:
        offset: int | None = None
        while True:
            try:
                updates = self.auditor_api.get_updates(offset=offset)
                for update in updates:
                    offset = int(update["update_id"]) + 1
                    message = update.get("message") or {}
                    self.handle_message(message)
            except Exception:
                time.sleep(3)


def load_cases(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("A matriz de perguntas está vazia")
    return data


def live_cases(cases: list[dict]) -> list[dict]:
    selected = [case for case in cases if case.get("live")]
    if not selected:
        raise ValueError("A matriz não contém casos marcados para homologação ao vivo")
    return selected


def coordinator_from_environment(root: Path) -> TelegramDemoCoordinator:
    required = {
        "TELEGRAM_AUDITOR_TOKEN": os.getenv("TELEGRAM_AUDITOR_TOKEN", ""),
        "TELEGRAM_ATENDENTE_TOKEN": os.getenv("TELEGRAM_ATENDENTE_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError("Variáveis ausentes: " + ", ".join(missing))

    service = RAGService(
        pdf_path=root / "data" / "politica_reembolsos_devolucoes_bimbam_buy.pdf",
        index_path=root / "data" / "vector_index.json",
    )
    return TelegramDemoCoordinator(
        service=service,
        auditor_api=TelegramAPI(required["TELEGRAM_AUDITOR_TOKEN"]),
        attendant_api=TelegramAPI(required["TELEGRAM_ATENDENTE_TOKEN"]),
        chat_id=required["TELEGRAM_CHAT_ID"],
        test_cases=live_cases(load_cases(root / "data" / "perguntas_teste.json")),
        allowed_user_id=os.getenv("TELEGRAM_ALLOWED_USER_ID", ""),
    )
