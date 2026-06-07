#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STORAGE_ROOT="$PROJECT_DIR/storage"
APPLY=false
FRESH_RUNTIME=false

CANONICAL_DATASETS=(
  roles
  users
  authors
  author_watchlist_instruments
  lead_sources
  instruments
  strategies
  bundles
  bundle_members
  products
  promo_codes
  legal_documents
  payments
  subscriptions
  user_consents
  audit_events
  recommendations
  recommendation_legs
  recommendation_attachments
)

LEGACY_DIRS=(
  json
  blob
  uploads
  minio
  tmp
  previews
)

usage() {
  cat <<'EOF'
Usage:
  bash scripts/clean_storage.sh [--apply] [--fresh-runtime] [--root /path/to/storage]

Options:
  --apply          perform deletion; without it the script prints a dry-run plan
  --fresh-runtime  fully clear storage/runtime/json and storage/runtime/blob
  --root PATH      override storage root (default: ./storage)
EOF
}

run_or_print() {
  if [ "$APPLY" = true ]; then
    "$@"
  else
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply)
      APPLY=true
      shift
      ;;
    --fresh-runtime)
      FRESH_RUNTIME=true
      shift
      ;;
    --root)
      STORAGE_ROOT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ -z "$STORAGE_ROOT" ]; then
  echo "Storage root must not be empty" >&2
  exit 1
fi

RUNTIME_JSON="$STORAGE_ROOT/runtime/json"
RUNTIME_BLOB="$STORAGE_ROOT/runtime/blob"

mkdir -p "$STORAGE_ROOT"

for legacy_dir in "${LEGACY_DIRS[@]}"; do
  legacy_path="$STORAGE_ROOT/$legacy_dir"
  if [ -e "$legacy_path" ]; then
    run_or_print rm -rf "$legacy_path"
  fi
done

if [ -d "$RUNTIME_JSON" ]; then
  while IFS= read -r runtime_file; do
    filename="$(basename "$runtime_file" .json)"
    keep=false
    for dataset in "${CANONICAL_DATASETS[@]}"; do
      if [ "$dataset" = "$filename" ]; then
        keep=true
        break
      fi
    done
    if [ "$keep" = false ]; then
      run_or_print rm -f "$runtime_file"
    fi
  done < <(find "$RUNTIME_JSON" -maxdepth 1 -type f -name '*.json' | sort)
fi

if [ "$FRESH_RUNTIME" = true ]; then
  if [ -d "$RUNTIME_JSON" ]; then
    while IFS= read -r runtime_file; do
      run_or_print rm -f "$runtime_file"
    done < <(find "$RUNTIME_JSON" -maxdepth 1 -type f -name '*.json' | sort)
  fi
  if [ -d "$RUNTIME_BLOB" ]; then
    while IFS= read -r blob_path; do
      run_or_print rm -rf "$blob_path"
    done < <(find "$RUNTIME_BLOB" -mindepth 1 -maxdepth 1 | sort)
  fi
fi

run_or_print mkdir -p "$RUNTIME_JSON" "$RUNTIME_BLOB"

if [ "$APPLY" = true ]; then
  echo "Storage cleanup completed for $STORAGE_ROOT"
else
  echo "Dry-run completed for $STORAGE_ROOT"
fi
