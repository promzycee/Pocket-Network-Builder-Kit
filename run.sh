#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
set -a
[ ! -f .env ] || . ./.env
set +a
if command -v python3 >/dev/null 2>&1; then
  exec python3 -u server.py
fi
exec python -u server.py
