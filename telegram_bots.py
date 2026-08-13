"""Inicializa os dois bots de homologação do Telegram."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from bimbam_rag.telegram_demo import coordinator_from_environment  # noqa: E402


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    coordinator_from_environment(ROOT).poll_forever()

