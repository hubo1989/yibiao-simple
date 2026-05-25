#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.docker.example}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for this smoke check" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 1
fi

if [[ ! -f "$ROOT_DIR/frontend/build/index.html" ]]; then
  echo "frontend/build/index.html not found; run 'cd frontend && npm ci && npm run build' first" >&2
  exit 1
fi

compose_config="$(cd "$ROOT_DIR" && docker compose --env-file "$ENV_FILE" config)"

required_refs=(
  "DB_PORT"
  "LLM_BASE_URL"
  "LLM_API_KEY"
  "LLM_MODEL"
  "EMBEDDING_PROVIDER"
  "EMBEDDING_BASE_URL"
  "EMBEDDING_MODEL"
)

for name in "${required_refs[@]}"; do
  if ! grep -q "$name" "$ROOT_DIR/.env.docker.example" "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/README.md" "$ROOT_DIR/docker-compose.yml"; then
    echo "missing self-hosting config reference: $name" >&2
    exit 1
  fi
done

required_compose_names=(
  "LLM_BASE_URL"
  "LLM_API_KEY"
  "LLM_MODEL"
  "EMBEDDING_PROVIDER"
  "EMBEDDING_BASE_URL"
  "EMBEDDING_MODEL"
)

for name in "${required_compose_names[@]}"; do
  if ! grep -q "$name" <<<"$compose_config"; then
    echo "docker compose config does not expose: $name" >&2
    exit 1
  fi
done

if ! grep -q "pgvector/pgvector" <<<"$compose_config"; then
  echo "docker compose config must use a PostgreSQL image with pgvector support" >&2
  exit 1
fi

echo "self-host smoke ok: frontend build exists and docker compose config exposes DB, LLM and embedding settings"
