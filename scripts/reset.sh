#!/usr/bin/env bash
# Локальный воспроизводимый сброс для текущего file-mode runbook
set -euo pipefail
bash scripts/clean_storage.sh --apply --fresh-runtime
echo "Сброс завершён. Дальше используйте команды локального запуска из doc/README.md"
