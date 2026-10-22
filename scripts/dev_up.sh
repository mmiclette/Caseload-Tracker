#!/usr/bin/env bash
#
# Bring the whole local stack up: Postgres, the API, and the frontend.
#
#   bash scripts/dev_up.sh          # demo database (realistic, dated to today)
#   bash scripts/dev_up.sh pressure # pressure-test database
#   bash scripts/dev_up.sh reseed   # demo database, re-seeded from scratch
#
# Exists because this stack has three moving parts and Docker Desktop
# quitting between sessions has broken it repeatedly — including cases where
# the API kept answering /health while its database connection was dead, so
# the app looked up and wasn't.
#
# Note the port: the container publishes 5433, not 5432, because a native
# Postgres on this machine binds 127.0.0.1:5432 and shadows Docker. See the
# comment in docker-compose.yml.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-demo}"
DB_NAME="cocm_registry_demo"
[ "$MODE" = "pressure" ] && DB_NAME="cocm_registry_pressure"
DB_URL="postgresql+psycopg://cocm:cocm_local_dev@localhost:5433/${DB_NAME}"
LOG_DIR="${TMPDIR:-/tmp}/cocm-dev"
mkdir -p "$LOG_DIR"

say() { printf '\n\033[1m%s\033[0m\n' "$1"; }

say "1/4  Docker"
if ! docker info >/dev/null 2>&1; then
  echo "      daemon not running — launching Docker Desktop"
  open -a Docker
  for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || { echo "      Docker did not start; open it manually"; exit 1; }
fi
echo "      ok"

say "2/4  Postgres (localhost:5433)"
docker compose up -d >/dev/null
for _ in $(seq 1 30); do
  docker exec cocm_registry_postgres pg_isready -U cocm -d cocm_registry >/dev/null 2>&1 && break
  sleep 2
done
docker exec cocm_registry_postgres pg_isready -U cocm -d cocm_registry >/dev/null 2>&1 \
  || { echo "      Postgres never became ready"; exit 1; }

if [ "$MODE" = "reseed" ]; then
  echo "      dropping and recreating $DB_NAME"
  docker exec cocm_registry_postgres psql -U cocm -d cocm_registry \
    -c "DROP DATABASE IF EXISTS ${DB_NAME}" -c "CREATE DATABASE ${DB_NAME}" >/dev/null
fi
DATABASE_URL="$DB_URL" python3 -m alembic upgrade head >/dev/null 2>&1
echo "      $DB_NAME migrated to head"

if [ "$MODE" = "reseed" ]; then
  DATABASE_URL="$DB_URL" PYTHONPATH=. python3 scripts/seed_demo.py 2>/dev/null | tail -n +2
fi

say "3/4  API (127.0.0.1:8000)"
lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
sleep 1
DATABASE_URL="$DB_URL" nohup python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
  > "$LOG_DIR/api.log" 2>&1 &
for _ in $(seq 1 20); do curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1 && break; sleep 1; done
# /health doesn't touch the database, so check a real query too — an API that
# answers /health with a dead connection is exactly the failure this script
# is meant to stop hiding.
# No -f here: a 401 is the SUCCESS case (the credentials are deliberately
# bogus), and curl -f would treat that 401 as a failure.
PROBE=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  "http://127.0.0.1:8000/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"__probe__@invalid","password":"__probe__"}' 2>/dev/null || true)
if [ "$PROBE" = "401" ]; then
  echo "      ok — database reachable"
else
  echo "      API answered /health but a real database query returned HTTP $PROBE"
  echo "      check $LOG_DIR/api.log"
  exit 1
fi

say "4/4  Frontend (localhost:5173)"
lsof -tiTCP:5173 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
sleep 1
(cd frontend && nohup npm run dev > "$LOG_DIR/vite.log" 2>&1 &)
for _ in $(seq 1 30); do curl -sf http://localhost:5173/ >/dev/null 2>&1 && break; sleep 1; done
curl -sf http://localhost:5173/ >/dev/null 2>&1 && echo "      ok" \
  || { echo "      Vite did not start; check $LOG_DIR/vite.log"; exit 1; }

cat <<EOF

Ready — http://localhost:5173   (database: ${DB_NAME})

  priya@neuroflow.com / demo-password    care manager, 6 patients
  dana@neuroflow.com  / demo-password    care manager, 3 patients (one flagged)
  demo@neuroflow.com  / demo-password    supervisor, for the reports

Logs: $LOG_DIR/{api,vite}.log
EOF
