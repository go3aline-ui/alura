"""Validação rápida do deploy público e da saúde do contêiner."""

from __future__ import annotations

import sys
import urllib.request


def fetch(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def main() -> None:
    base_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8502"
    health_status, health_body = fetch(base_url + "/_stcore/health")
    page_status, page_body = fetch(base_url + "/")
    if health_status != 200 or health_body.strip() != "ok":
        raise SystemExit("Healthcheck inválido")
    if page_status != 200 or "streamlit" not in page_body.lower():
        raise SystemExit("Página principal inválida")
    print(f"Deploy verificado com sucesso em {base_url}")


if __name__ == "__main__":
    main()

