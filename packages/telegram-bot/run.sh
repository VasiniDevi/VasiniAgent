#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p data

echo "Starting Wellness CBT Telegram Bot..."
python3 -m wellness_bot.app
