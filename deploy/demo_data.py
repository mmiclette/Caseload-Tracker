"""
Keeps the hosted prototype's demo data anchored to today.

scripts/seed_demo.py already dates everything relative to the day it runs
(``days_ago(16)``, ``months_ago(3)``) rather than to fixed calendar dates.
That is exactly the property the hosted demo needs — "always X days from
today" — but it only holds on the day the seed ran. A database seeded in
March shows a caseload whose most recent contact was months ago: every
score carries a staleness asterisk, every reminder is wildly overdue, and
Quality Metrics trails off into empty months.

So this module records *when* the seed last ran and re-runs it whenever
that date is no longer today. A visitor always lands on a caseload whose
reminders are due this week and whose scores were taken days ago, however
long the service has been deployed.

**Why the state table is not an Alembic migration.** ``demo_state`` is
deployment bookkeeping, not registry schema. The registry's own schema has
to run unmodified against Postgres and Snowflake (see CLAUDE.md's
portability rule) and is versioned by Alembic; putting a demo-only table in
that chain would ship a table to every environment that has no use for it.
It is created here instead, with plain SQLAlchemy Core DDL that works on
SQLite and Postgres alike, and lives outside ``Base.metadata`` so the wipe
below cannot delete the very row recording that the wipe happened.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from datetime import date
from pathlib import Path

from sqlalchemy import Column, Date, MetaData, String, Table, delete, insert, select
from sqlalchemy.engine import Engine

ROOT = Path(__file__).resolve().parents[1]

_metadata = MetaData()

demo_state = Table(
    "demo_state",
    _metadata,
    # Single-row table; the constant key makes that explicit and makes the
    # upsert a plain delete-then-insert rather than anything dialect-specific
    # (no ON CONFLICT — same rule the registry's repositories follow).
    Column("state_key", String(32), primary_key=True),
    Column("seeded_on", Date, nullable=False),
)

_STATE_KEY = "demo_seed"

# Serialises re-seeding. FastAPI runs sync routes in a threadpool, so two
# visitors arriving just after midnight could otherwise both see stale data
# and both start a wipe-and-seed — racing each other into duplicated or
# half-written rows. One process, one worker, so a threading lock is the
# right scope; a multi-worker deployment would need a database-level lock.
_seed_lock = threading.Lock()


def ensure_state_table(engine: Engine) -> None:
    """Create ``demo_state`` if it isn't there yet. Safe to call every boot."""
    _metadata.create_all(engine, tables=[demo_state])


def ensure_schema(engine: Engine) -> str:
    """
    Build the registry schema, by whichever route the dialect supports.

    **On SQLite: from the models, not the Alembic chain.** Migration
    ``a3613a105946`` issues ``ALTER COLUMN ... DROP DEFAULT``, which SQLite
    has no syntax for, so ``alembic upgrade head`` cannot run there at all.
    That is not a defect in the migrations — they are written for the two
    databases this registry actually targets (Postgres in dev and test,
    Snowflake in production), and SQLite is neither.

    ``create_all`` is the right substitute specifically because a demo
    database has no history to migrate: it is built from empty on every
    boot, so the only thing that matters is arriving at the schema the
    models describe. It is also the route the test suite already takes —
    tests/conftest.py builds its SQLite schema exactly this way, so the 195
    passing tests are evidence that the models do produce a working schema
    on this dialect.

    The tradeoff worth stating plainly: a hosted demo running on SQLite
    exercises the models but **not** the migration chain. A migration that
    drifted from the models would not be caught here. Postgres remains the
    place that gets verified, via the clean upgrade/downgrade round-trip and
    from-scratch chain replay described in CLAUDE.md.

    Returns which route was taken, for the boot log.
    """
    from app.database import Base
    import app.models  # noqa: F401  — registers every model on Base.metadata

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
        return "create_all (sqlite)"

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        check=True,
    )
    return "alembic upgrade head"


def seeded_on(engine: Engine) -> date | None:
    """The date the demo data was last seeded, or None if it never was."""
    ensure_state_table(engine)
    with engine.connect() as conn:
        row = conn.execute(
            select(demo_state.c.seeded_on).where(demo_state.c.state_key == _STATE_KEY)
        ).first()
    if row is None:
        return None
    value = row[0]
    # SQLite hands back a date; some drivers hand back a datetime.
    return value.date() if hasattr(value, "date") and not isinstance(value, date) else value


def _record_seed(engine: Engine, on: date) -> None:
    with engine.begin() as conn:
        conn.execute(delete(demo_state).where(demo_state.c.state_key == _STATE_KEY))
        conn.execute(insert(demo_state).values(state_key=_STATE_KEY, seeded_on=on))


def wipe(engine: Engine) -> None:
    """
    Delete every registry row, leaving the schema in place.

    Reverse ``sorted_tables`` order so foreign keys are satisfied without
    needing to disable constraints — which is a per-dialect incantation we'd
    rather not write. ``alembic_version`` and ``demo_state`` are not in
    ``Base.metadata``, so both survive: the schema stays migrated to head and
    the seed marker is rewritten explicitly by the caller.
    """
    from app.database import Base
    import app.models  # noqa: F401  — registers every model on Base.metadata

    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(delete(table))


def run_seed() -> None:
    """
    Run scripts/seed_demo.py in a subprocess.

    A subprocess rather than an import because the seed is a top-level
    script, not a function — it executes on import and calls ``sys.exit`` on
    a guard failure. Running it as the command line does keeps this module
    from depending on the seed's internal shape, so the seed stays free to
    change without breaking the deploy.
    """
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "seed_demo.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"seed_demo.py failed with exit code {result.returncode}")


def ensure_fresh(engine: Engine, *, force: bool = False) -> bool:
    """
    Re-seed if the demo data isn't anchored to today.

    Returns True if a re-seed happened, False if the data was already fresh.
    """
    today = date.today()
    if not force and seeded_on(engine) == today:
        return False

    with _seed_lock:
        # Re-check inside the lock: whoever held it may have just done the
        # work, in which case the second caller should not seed again.
        if not force and seeded_on(engine) == today:
            return False
        wipe(engine)
        run_seed()
        _record_seed(engine, today)
    return True
