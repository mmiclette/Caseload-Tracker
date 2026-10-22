"""
HTTP-level auth tests. Every other route test file exercises services and
repositories directly and never touches FastAPI's dependency graph — auth
is the first thing in this codebase that only matters at the route layer
(get_current_provider is a router-level dependency, not something a
service call goes through), so this is the one file that drives requests
through a real TestClient, with get_db overridden to the same db_session
fixture every other test uses.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models.enums import ProviderRole
from app.models.provider import Provider
from app.repositories.provider import ProviderRepository

PROVIDER_EMAIL = "provider@example.com"
PROVIDER_PASSWORD = "correct-password"


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def make_provider(db_session, email=PROVIDER_EMAIL, password=PROVIDER_PASSWORD):
    return ProviderRepository(db_session).create(
        Provider(
            name="Auth Test Provider",
            role=ProviderRole.CLINIC_SUPERVISOR,
            email=email,
            hashed_password=hash_password(password),
        )
    )


def test_protected_route_rejects_missing_token(client):
    response = client.get("/patients")
    assert response.status_code == 401


def test_health_check_does_not_require_a_token(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_login_accepts_oauth2_form_encoding(db_session, client):
    """
    The docs console's Authorize dialog (and any standard OAuth2 password
    client) posts form-encoded username/password — see routes/auth.py.
    """
    make_provider(db_session)

    response = client.post(
        "/auth/login",
        data={"username": PROVIDER_EMAIL, "password": PROVIDER_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_with_correct_credentials_issues_token(db_session, client):
    make_provider(db_session)

    response = client.post(
        "/auth/login", json={"email": PROVIDER_EMAIL, "password": PROVIDER_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert body["provider"]["email"] == PROVIDER_EMAIL
    assert "hashed_password" not in body["provider"]


def test_login_with_wrong_password_is_rejected(db_session, client):
    make_provider(db_session)

    response = client.post(
        "/auth/login", json={"email": PROVIDER_EMAIL, "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_login_with_unknown_email_is_rejected(client):
    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401


def test_provider_without_a_password_cannot_log_in(db_session, client):
    """A Provider created without credentials (e.g. via the CTMS's account
    types that never log in directly) simply can't authenticate."""
    ProviderRepository(db_session).create(
        Provider(name="No Login", role=ProviderRole.DATA_ANALYST, email="no-login@example.com")
    )

    response = client.post(
        "/auth/login", json={"email": "no-login@example.com", "password": "anything"}
    )
    assert response.status_code == 401


def test_valid_token_grants_access_to_a_protected_route(db_session, client):
    make_provider(db_session)
    token = client.post(
        "/auth/login", json={"email": PROVIDER_EMAIL, "password": PROVIDER_PASSWORD}
    ).json()["access_token"]

    response = client.get("/patients", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_garbage_token_is_rejected(client):
    response = client.get("/patients", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
