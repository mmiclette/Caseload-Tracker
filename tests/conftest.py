"""
Test fixtures.

Tests run against the real Postgres instance defined by DATABASE_URL (the
same docker-compose Postgres service used locally) rather than SQLite or
mocks, per Phase 1 scope ("running against the docker-compose Postgres
instance"). Each test gets a fresh schema: we create all tables before the
test and drop them after, inside a dedicated test database so this never
touches dev data.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    # Port 5433, matching docker-compose.yml's remap — a native Postgres on
    # the dev machine binds 5432 and shadows the container, so the old
    # default here failed every test with "role cocm does not exist".
    "postgresql+psycopg://cocm:cocm_local_dev@localhost:5433/cocm_registry_test",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, future=True)
    import app.models  # noqa: F401  ensure models are registered on Base.metadata

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_local()
    try:
        yield session
    finally:
        # Roll back and clear all rows between tests so each test starts clean
        # without paying the cost of recreating the schema every time.
        session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()
