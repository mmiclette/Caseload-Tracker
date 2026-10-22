"""
HTTP-level test for the Monthly Time Tracker route's org-configuration
gate. The gate (checking settings.monthly_time_tracker_enabled and
returning 404 vs. 200) lives in the route function itself, not in a
service -- build_monthly_time_tracker never looks at settings -- so this
is the one thing about this report that can't be verified by calling the
service directly, the same reasoning test_auth.py gives for using a real
TestClient instead of testing services/repos directly.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models.enums import ProviderRole
from app.models.provider import Provider
from app.repositories.provider import ProviderRepository


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def authenticated_headers(db_session, client):
    ProviderRepository(db_session).create(
        Provider(
            name="Time Tracker Route Test Provider",
            role=ProviderRole.CLINIC_SUPERVISOR,
            email="time-tracker-route@example.com",
            hashed_password=hash_password("correct-password"),
        )
    )
    response = client.post(
        "/auth/login", json={"email": "time-tracker-route@example.com", "password": "correct-password"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_time_tracker_available_by_default(db_session, client):
    headers = authenticated_headers(db_session, client)
    response = client.get("/reports/time-tracker", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_time_tracker_returns_404_when_disabled(db_session, client):
    headers = authenticated_headers(db_session, client)
    original = settings.monthly_time_tracker_enabled
    settings.monthly_time_tracker_enabled = False
    try:
        response = client.get("/reports/time-tracker", headers=headers)
        assert response.status_code == 404
    finally:
        settings.monthly_time_tracker_enabled = original
