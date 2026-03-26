#!/usr/bin/env bash

set -euo pipefail

export APP_ENV="${APP_ENV:-development}"
export APP_HOST="${APP_HOST:-127.0.0.1}"
export APP_PORT="${APP_PORT:-8011}"
export BASE_URL="${BASE_URL:-http://127.0.0.1:8011}"
export ADMIN_BASE_URL="${ADMIN_BASE_URL:-http://127.0.0.1:8011/admin}"
export APP_DATA_MODE="${APP_DATA_MODE:-file}"
export APP_PREVIEW_ENABLED="${APP_PREVIEW_ENABLED:-true}"
export APP_STORAGE_ROOT="${APP_STORAGE_ROOT:-storage}"
export APP_SECRET_KEY="${APP_SECRET_KEY:-local-app-secret}"
export INTERNAL_API_SECRET="${INTERNAL_API_SECRET:-local-internal-secret}"
export TELEGRAM_USE_WEBHOOK="${TELEGRAM_USE_WEBHOOK:-false}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-__FILL_ME__}"
export TELEGRAM_BOT_USERNAME="${TELEGRAM_BOT_USERNAME:-preview_bot}"
