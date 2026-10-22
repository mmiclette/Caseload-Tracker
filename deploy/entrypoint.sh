#!/usr/bin/env bash
#
# Container entrypoint for the hosted prototype.
#
#   1. migrate to head
#   2. re-seed if the demo data isn't anchored to today
#   3. serve
#
# Step 2 is what makes the demo "always X days from today" — see
# deploy/demo_data.py for why it is a re-seed rather than stored offsets.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${DATABASE_URL:?DATABASE_URL must be set}"
: "${PORT:=8000}"
# Set in the image too, but defaulted here so the script also runs straight
# from a checkout.
export PYTHONPATH="${PYTHONPATH:-$(pwd)}"

# scripts/seed_demo.py refuses to run unless DATABASE_URL names a dedicated
# demo database — a deliberate guard against seeding over real data. Fail
# here with a clear message rather than letting the seed exit mid-boot.
case "$DATABASE_URL" in
  *demo*) ;;
  *) echo "DATABASE_URL must contain 'demo' — this image only ever hosts demo data." >&2
     exit 1 ;;
esac

if [ "${SECRET_KEY:-}" = "" ]; then
  echo "SECRET_KEY is not set. It signs provider JWTs; the default in" >&2
  echo "app/core/config.py is a dev-only placeholder and must not ship." >&2
  exit 1
fi

echo "==> preparing database"
python3 - <<'PY'
from app.database import engine
from deploy import demo_data

print(f"    schema via {demo_data.ensure_schema(engine)}")
if demo_data.ensure_fresh(engine):
    print("    re-seeded and re-anchored to today")
else:
    print("    already anchored to today")
PY

echo "==> serving on :$PORT"
exec python3 -m uvicorn deploy.demo_app:demo --host 0.0.0.0 --port "$PORT"
