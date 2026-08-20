#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

BIND_HOST="${BIND_HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PYTHON="${PYTHON:-$PROJECT_ROOT/.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "未找到 Python 虚拟环境：$PYTHON" >&2
  exit 1
fi

exec "$PYTHON" -m uvicorn api_app:app --host "$BIND_HOST" --port "$PORT"
