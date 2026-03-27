#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -f "$SCRIPT_DIR/local_file_profile.sh" ]; then
  # shellcheck disable=SC1090
  source "$SCRIPT_DIR/local_file_profile.sh"
fi

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

check_url() {
  local url="$1"
  printf 'checking %s\n' "$url"
  curl -fsS "$url" >/dev/null
}

check_url "$BASE_URL/health"
check_url "$BASE_URL/preview"
check_url "$BASE_URL/preview/app/catalog"
check_url "$BASE_URL/preview/app/status"
check_url "$BASE_URL/preview/app/help"
check_url "$BASE_URL/preview/app/payments"
check_url "$BASE_URL/preview/app/payments/preview-payment-1"
check_url "$BASE_URL/preview/app/subscriptions"
check_url "$BASE_URL/preview/app/subscriptions/preview-subscription-1"
check_url "$BASE_URL/preview/admin/dashboard"
check_url "$BASE_URL/preview/author/dashboard"

printf 'local file-mode smoke check ok\n'
