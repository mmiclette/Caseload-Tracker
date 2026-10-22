"""
The hosted-prototype entry point: one process serving both the API and the
built frontend.

Deliberately additive. Nothing under ``app/`` or ``frontend/src/`` changes to
support hosting — this module wraps them:

* The existing FastAPI app is mounted at ``/api``. The frontend's API client
  already calls ``/api/*`` (that's what the Vite dev proxy rewrites in
  development), so mounting at that prefix means **zero changes to the
  client and zero to the routers**. It also makes the deployment
  same-origin, so there is no CORS configuration to get wrong.
* The built SPA is served from ``frontend/dist`` with an index.html fallback,
  because the frontend uses client-side routing — a visitor opening
  ``/reports/drr`` directly must receive the app, not a 404.

Run with::

    uvicorn deploy.demo_app:demo --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.deps import get_current_provider
from app.database import engine
from app.main import app as api_app
from deploy import demo_data

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"


# --------------------------------------------------------------------------
# Demo controls, exposed on the API app so they land under /api/demo/*.
#
# Authenticated like every other router. CLAUDE.md keeps the list of
# unauthenticated routes to exactly two (POST /auth/login, GET /health) and
# says it should stay a short deliberate list rather than grow by accident —
# a public reset button anyone could spam is not a good enough reason to make
# it three. Testers are signed in already.
# --------------------------------------------------------------------------
demo_router = APIRouter(
    prefix="/demo",
    tags=["demo"],
    dependencies=[Depends(get_current_provider)],
)


@demo_router.get("/status")
def demo_status():
    """When the demo data was last re-anchored, and whether that is today."""
    anchored = demo_data.seeded_on(engine)
    return {
        "seeded_on": anchored.isoformat() if anchored else None,
        "today": date.today().isoformat(),
        "is_fresh": anchored == date.today(),
    }


@demo_router.post("/reset")
def demo_reset():
    """
    Wipe and re-seed, re-anchoring every date to today.

    Useful after a tester has been clicking around: it puts the scenario
    back to the known starting state described in scripts/seed_demo.py.
    """
    demo_data.ensure_fresh(engine, force=True)
    return demo_status()


api_app.include_router(demo_router)


# --------------------------------------------------------------------------
# The outer app: API under /api, SPA everywhere else.
# --------------------------------------------------------------------------
demo = FastAPI(
    title="CoCM Registry — hosted prototype",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

demo.mount("/api", api_app)


@demo.get("/healthz")
def healthz():
    """Platform health check, outside the mounted API's own /api/health."""
    return {"status": "ok"}


if DIST.is_dir():

    demo.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @demo.get("/{full_path:path}")
    def spa(full_path: str):
        """
        Serve a real file when the path names one, otherwise index.html.

        The fallback is what makes client-side routes work on a hard refresh.
        Re-anchoring is checked here rather than on API requests so a stale
        database is refreshed when someone *opens* the app, never underneath
        an in-flight session's API traffic.
        """
        if os.environ.get("DEMO_REANCHOR_ON_LOAD", "1") == "1":
            demo_data.ensure_fresh(engine)

        candidate = (DIST / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(DIST):
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")

else:

    @demo.get("/{full_path:path}")
    def no_build(full_path: str):
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Frontend build missing. Run `npm run build` in frontend/ "
                    "so that frontend/dist/index.html exists."
                )
            },
        )
