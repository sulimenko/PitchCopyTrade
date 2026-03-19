#!/usr/bin/env bash
# =============================================================================
# deploy/migrate.sh — создание схемы БД и полный сброс
#
# Использование:
#   bash deploy/migrate.sh          # применить схему (идемпотентно если база пустая)
#   bash deploy/migrate.sh --reset  # полный сброс: БД + runtime JSON/blob → пересоздать
#
# Требования:
#   - PostgreSQL установлен локально
#   - Пользователь и база созданы (см. README.md Шаг 2)
#   - .env.server содержит POSTGRES_USER и POSTGRES_DB
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env.server"
SCHEMA_FILE="$SCRIPT_DIR/schema.sql"
STORAGE_RUNTIME="$PROJECT_DIR/storage/runtime"

if [ ! -f "$ENV_FILE" ]; then
  echo "Ошибка: файл $ENV_FILE не найден"
  exit 1
fi

# Читаем POSTGRES_USER и POSTGRES_DB из .env.server
PG_USER=$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_DB=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_PASS=$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")

if [ -z "$PG_USER" ] || [ -z "$PG_DB" ]; then
  echo "Ошибка: POSTGRES_USER и POSTGRES_DB должны быть заполнены в .env.server"
  exit 1
fi

if [ "${1:-}" = "--reset" ]; then
  echo "=== ПОЛНЫЙ СБРОС ==="
  echo ""

  echo "1. Сбрасываем схему БД ($PG_DB)..."
  sudo -u postgres psql -d "$PG_DB" << SQL
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO "$PG_USER";
GRANT ALL ON SCHEMA public TO public;
SQL
  echo "   Готово."
  echo ""

  echo "2. Очищаем storage/runtime/json/ ..."
  if [ -d "$STORAGE_RUNTIME/json" ]; then
    rm -f "$STORAGE_RUNTIME"/json/*.json
    echo "   Удалены JSON-файлы."
  else
    echo "   Директория не найдена, пропускаем."
  fi
  echo ""

  echo "3. Очищаем storage/runtime/blob/ ..."
  if [ -d "$STORAGE_RUNTIME/blob" ]; then
    find "$STORAGE_RUNTIME/blob" -type f -delete
    echo "   Удалены blob-файлы."
  else
    echo "   Директория не найдена, пропускаем."
  fi
  echo ""

  echo "4. Применяем схему..."
fi

# sudo -u postgres psql -d "$PG_DB" -f "$SCHEMA_FILE"
PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U "$PG_USER" -d "$PG_DB" -f "$SCHEMA_FILE"

echo ""
echo "Готово. Таблицы в базе $PG_DB:"
# sudo -u postgres psql -d "$PG_DB" -c "\dt" 2>/dev/null | grep -v "^$" || true
PGPASSWORD="$PG_PASS" psql -h 127.0.0.1 -U "$PG_USER" -d "$PG_DB" -c "\dt" 2>/dev/null | grep -v "^$" || true
