#!/usr/bin/env bash
# Levanta el servidor FastAPI + widget.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
exec python -m uvicorn app.main:app --host "${SPA_HOST:-127.0.0.1}" --port "${SPA_PORT:-8088}" "$@"
