#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Paths relative to admin-api directory
export DB_PATH="${DB_PATH:-../telegram-bot/data/wellness.db}"
export PACK_DIR="${PACK_DIR:-../../packs/wellness-cbt}"
export ENV_PATH="${ENV_PATH:-../telegram-bot/.env}"
export ADMIN_TOKEN="${ADMIN_TOKEN:-$(grep ADMIN_TOKEN ../telegram-bot/.env 2>/dev/null | cut -d= -f2 || echo 'change-me')}"

echo "Starting Admin API on :8080..."
echo "  DB_PATH=$DB_PATH"
echo "  PACK_DIR=$PACK_DIR"
echo "  ENV_PATH=$ENV_PATH"

uvicorn admin_api.app:app --host 0.0.0.0 --port 8080 --reload
