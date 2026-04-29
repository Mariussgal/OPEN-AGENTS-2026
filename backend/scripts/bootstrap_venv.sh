#!/usr/bin/env bash
# Installe ou recrée le venv avec Python 3.10+ et fait ``pip install -e .``.
# Usage :
#   bash scripts/bootstrap_venv.sh           # utilise .venv s'il existe déjà (active-le ensuite)
#   bash scripts/bootstrap_venv.sh --recreate # supprime .venv puis recrée
set -euo pipefail
cd "$(dirname "$0")/.."

pick_python() {
  for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
      ver=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
      major=${ver%%.*}
      minor=${ver#*.}
      if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 10 ]; then
        echo "$cmd"
        return 0
      fi
    fi
  done
  echo ""
  return 1
}

PY="$(pick_python)" || true
if [ -z "$PY" ]; then
  echo "Aucun Python 3.10+ dans le PATH."
  echo "Exemple : brew install python@3.11"
  exit 1
fi

echo "Python : $PY ($($PY --version))"

if [ "${1:-}" = "--recreate" ]; then
  echo "Suppression de .venv …"
  rm -rf .venv
fi

if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
echo
echo "Prêt. Active le venv puis lance l'API :"
echo "  source .venv/bin/activate"
echo "  python -m uvicorn server:app --host 127.0.0.1 --port 8000"
