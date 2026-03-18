#!/usr/bin/env bash
# =============================================================================
# deploy/migrate.sh — миграции и полный сброс БД + runtime-хранилища
#
# Использование:
#   bash deploy/migrate.sh              # применить новые миграции
#   bash deploy/migrate.sh --reset      # сбросить всё и накатить с нуля
#   bash deploy/migrate.sh downgrade -1 # откатить последнюю миграцию
#
# Требования:
#   - .env.server в корне проекта (ALEMBIC_DATABASE_URL, POSTGRES_USER, POSTGRES_DB)
#   - Docker образ собран: docker compose -f deploy/docker-compose.server.yml build
#   - PostgreSQL установлен локально, пользователь и база созданы заранее
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env.server"
STORAGE_RUNTIME="$PROJECT_DIR/storage/runtime"

if [ ! -f "$ENV_FILE" ]; then
  echo "Ошибка: файл $ENV_FILE не найден"
  echo "Скопируйте deploy/env.server.example в .env.server и заполните параметры"
  exit 1
fi

# Читаем нужные переменные из .env.server
POSTGRES_USER=$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
POSTGRES_DB=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")

if [ "${1:-}" = "--reset" ]; then
  echo "=== ПОЛНЫЙ СБРОС ==="
  echo ""

  # 1. Сбросить схему PostgreSQL
  echo "1. Сбрасываем схему БД ($POSTGRES_DB)..."
  sudo -u postgres psql -d "$POSTGRES_DB" << SQL
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO "$POSTGRES_USER";
GRANT ALL ON SCHEMA public TO public;
SQL
  echo "   Схема сброшена."
  echo ""

  # 2. Очистить runtime JSON-файлы (данные файлового режима)
  echo "2. Очищаем storage/runtime/json/ ..."
  if [ -d "$STORAGE_RUNTIME/json" ]; then
    rm -f "$STORAGE_RUNTIME"/json/*.json
    echo "   Удалены JSON-файлы."
  else
    echo "   Директория не найдена, пропускаем."
  fi
  echo ""

  # 3. Очистить runtime blob-файлы (загруженные вложения)
  echo "3. Очищаем storage/runtime/blob/ ..."
  if [ -d "$STORAGE_RUNTIME/blob" ]; then
    find "$STORAGE_RUNTIME/blob" -type f -delete
    echo "   Удалены blob-файлы."
  else
    echo "   Директория не найдена, пропускаем."
  fi
  echo ""

  echo "4. Запускаем миграции..."
else
  ALEMBIC_CMD="${*:-upgrade head}"
  echo "Запуск: alembic $ALEMBIC_CMD"
fi

# Применить миграции через Docker с --network host (достаёт до localhost:5432)
docker run --rm \
  --network host \
  -v "$PROJECT_DIR:/app" \
  -w /app \
  --env-file "$ENV_FILE" \
  deploy-api \
  bash -c "PYTHONPATH=src alembic ${*:-upgrade head}"

echo ""
echo "Готово."
