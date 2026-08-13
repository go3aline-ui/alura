#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if [ ! -f .env ]; then
  echo "Arquivo .env ausente. Copie .env.example e configure as credenciais." >&2
  exit 1
fi

docker compose build web
docker compose up -d web

attempt=0
until curl -fsS http://127.0.0.1:8502/_stcore/health >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    docker compose logs --tail=100 web
    echo "A aplicação não ficou saudável no tempo esperado." >&2
    exit 1
  fi
  sleep 2
done

sudo install -m 0644 ops/nginx-alura.conf /etc/nginx/sites-available/alura-rag
sudo ln -sfn /etc/nginx/sites-available/alura-rag /etc/nginx/sites-enabled/alura-rag
sudo nginx -t
sudo systemctl reload nginx

echo "Deploy concluído: http://alura.147-15-123-74.sslip.io"

