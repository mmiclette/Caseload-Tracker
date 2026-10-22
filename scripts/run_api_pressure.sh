#!/usr/bin/env bash
# Runs the API against the pressure-test database (six patients of realistic
# mock data from scripts/pressure_test.py) for interactive UI testing.
# The LAN IP is used because a native Postgres shadows localhost:5432 on this
# machine (see CLAUDE.md / memory).
set -euo pipefail
cd "$(dirname "$0")/.."
HOSTIP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1)
export DATABASE_URL="postgresql+psycopg://cocm:cocm_local_dev@${HOSTIP}:5432/cocm_registry_pressure"
exec python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
