#!/usr/bin/env bash
# Démarre l'API locale (Python du venv local si présent).
cd "$(dirname "$0")/.." || exit 1
if [ -x ".venv/bin/python" ]; then
  exec .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000 "$@"
fi
exec python3 -m uvicorn server:app --host 127.0.0.1 --port 8000 "$@"
