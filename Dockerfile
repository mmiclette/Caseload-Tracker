# Hosted prototype image: builds the SPA, then serves it and the API from
# one Python process. See deploy/README.md for the whole picture.

# --------------------------------------------------------------------------
# 1. Build the frontend
# --------------------------------------------------------------------------
FROM node:22-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
# Turns on the sign-in page's one-click role picker and swaps the PHI notice
# for a "this is invented data" one. Only ever set here — the registry's own
# build is unaffected.
ENV VITE_DEMO_MODE=1
RUN npm run build


# --------------------------------------------------------------------------
# 2. Serve
# --------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/srv

WORKDIR /srv

# requirements.txt is used as-is rather than trimmed to a runtime subset.
# A second dependency list is a file that drifts quietly; for a prototype
# that tradeoff isn't worth the smaller image.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY deploy/ ./deploy/
COPY --from=frontend /build/dist/ ./frontend/dist/

# SQLite lives here. On a platform without a persistent disk this is
# ephemeral, which is fine and arguably correct for a demo: the entrypoint
# seeds an empty database on every boot, so a restart simply returns the
# scenario to its known starting state.
RUN mkdir -p /data
ENV DATABASE_URL=sqlite:////data/cocm_demo.db

RUN chmod +x deploy/entrypoint.sh
EXPOSE 8000
CMD ["./deploy/entrypoint.sh"]
