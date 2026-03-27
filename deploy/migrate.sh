#!/usr/bin/env bash
# =============================================================================
# deploy/migrate.sh — создание схемы БД и полный сброс
#
# Использование:
#   bash deploy/migrate.sh          # применить схему (идемпотентно если база пустая)
#   bash deploy/migrate.sh --reset  # полный сброс: БД + runtime JSON/blob → пересоздать
#
# Требования:
#   - PostgreSQL установлен локально или доступен по 127.0.0.1
#   - Пользователь и база созданы (см. README.md Шаг 2)
#   - .env содержит POSTGRES_USER, POSTGRES_DB, POSTGRES_PASSWORD
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"
SCHEMA_FILE="$SCRIPT_DIR/schema.sql"
CLEAN_STORAGE_SCRIPT="$PROJECT_DIR/scripts/clean_storage.sh"

if [ ! -f "$ENV_FILE" ]; then
  echo "Ошибка: файл $ENV_FILE не найден"
  exit 1
fi

# Читаем POSTGRES_USER, POSTGRES_DB, POSTGRES_PASSWORD из .env
PG_USER=$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_DB=$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_PASS=$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'")
PG_HOST=$(grep -E '^POSTGRES_HOST=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" || echo "127.0.0.1")
PG_PORT=$(grep -E '^POSTGRES_PORT=' "$ENV_FILE" | cut -d= -f2- | tr -d '"' | tr -d "'" || echo "5432")

if [ -z "$PG_USER" ] || [ -z "$PG_DB" ]; then
  echo "Ошибка: POSTGRES_USER и POSTGRES_DB должны быть заполнены в .env"
  exit 1
fi

if [ "${1:-}" = "--reset" ]; then
  echo "=== ПОЛНЫЙ СБРОС ==="
  echo ""

  echo "1. Сбрасываем схему БД ($PG_DB)..."
  PGPASSWORD="$PG_PASS" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" << SQL
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO "$PG_USER";
GRANT ALL ON SCHEMA public TO public;
SQL
  echo "   Готово."
  echo ""

  echo "2. Очищаем storage перед чистой миграцией..."
  bash "$CLEAN_STORAGE_SCRIPT" --apply --fresh-runtime --root "$PROJECT_DIR/storage"
  echo "   Готово."
  echo ""

  echo "3. Применяем схему..."
fi

PGPASSWORD="$PG_PASS" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -f "$SCHEMA_FILE"

echo ""
echo "Готово. Таблицы в базе $PG_DB:"
PGPASSWORD="$PG_PASS" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -c "\dt" 2>/dev/null | grep -v "^$" || true
