#!/usr/bin/env bash
set -euo pipefail

BASE_BRANCH=${BASE_BRANCH:-develop}
CHECK_MODE=${CHECK_MODE:-default}
PYTHON_BIN=${PYTHON_BIN:-./.venv/bin/python}

echo "==> project checks mode=$CHECK_MODE base=$BASE_BRANCH"

git diff --check

if [ ! -x "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  else
    echo "python is not available; only git diff checks were run"
    exit 0
  fi
fi

case "$CHECK_MODE" in
  default)
    "$PYTHON_BIN" -m compileall src tests
    ;;
  db)
    "$PYTHON_BIN" -m compileall src tests
    "$PYTHON_BIN" -m pytest -q
    ;;
  full)
    "$PYTHON_BIN" -m compileall src tests
    "$PYTHON_BIN" -m pytest -q
    ;;
  docs)
    echo "docs mode: git diff checks only"
    ;;
  *)
    echo "Unknown CHECK_MODE=$CHECK_MODE" >&2
    exit 2
    ;;
esac
