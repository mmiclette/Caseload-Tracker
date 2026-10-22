"""
Audit log (Phase 13).

CLAUDE.md's PHI rule: "Every write to patient status, a flag, or a score
gets an audit log entry recording who made the change, what changed, and
when." These tests cover each of those three, plus the episode lifecycle,
and — importantly — assert that the real HTTP routes supply the
authenticated provider as the actor. `actor` is an optional parameter so
scripts can write without one, which means a route that forgets to pass it
would silently log anonymous entries; test_routes_record_the_authenticated_actor
is what keeps that from happening quietly.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models.enums import (
    AuditAction,
    ConditionType,
    ContactType,
    MeasureType,
    ProviderRole,
    TreatmentStatusEnum,
)
from app.models.patient import Patient
from app.models.provider import Provider
from app.repositories.audit_log import AuditLogRepository
from app.repositories.patient import PatientRepository
from app.repositories.provider import ProviderRepository
from app.services.consultation_service import ConsultationService
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService

ACTOR_EMAIL = "audit-actor@example.com"
ACTOR_PASSWORD = "audit-test-password"


@pytest.fixture()
def actor(db_session):
    return ProviderRepository(db_session).create(
        Provider(
            name="Dr. Audit Actor",
            role=ProviderRole.CARE_MANAGER,
            email=ACTOR_EMAIL,
            hashed_password=hash_password(ACTOR_PASSWORD),
        )
    )


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


def make_patient(db_session, mrn="MRN-AUDIT-1"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Audit Test Patient",
            payer="Medicaid",
            date_of_birth=date(1984, 5, 9),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def entries(db_session, patient_id):
    return AuditLogRepository(db_session).list_by_patient(patient_id)


def actions(db_session, patient_id):
    return [e.action for e in entries(db_session, patient_id)]


# --- the three writes the PHI rule names -----------------------------------


def test_status_change_is_audited_with_before_and_after(db_session, actor):
    patient = make_patient(db_session)
    service = EpisodeService(db_session)
    episode = service.create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 1), actor=actor
    )
    service.transition_status(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        status=TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN,
        status_changed_date=date(2026, 3, 1),
        actor=actor,
    )

    status_entries = [
        e for e in entries(db_session, patient.patient_id) if e.action == AuditAction.STATUS_CHANGED
    ]
    # Newest first: the RPP transition, then the active_treatment one from
    # opening the episode.
    assert [e.new_value for e in status_entries] == ["relapse_prevention_plan", "active_treatment"]
    assert status_entries[0].old_value == "active_treatment"
    assert status_entries[1].old_value is None  # nothing preceded it
    assert status_entries[0].field == "status"
    assert status_entries[0].actor_provider_id == actor.provider_id
    assert status_entries[0].actor_label == "Dr. Audit Actor"
    assert status_entries[0].occurred_at is not None


def test_flag_set_and_cleared_are_distinct_audited_events(db_session, actor):
    patient = make_patient(db_session, "MRN-AUDIT-2")
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 1), actor=actor
    )
    ContactService(db_session).record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 2, 1),
        discuss_with_psychiatric_consultant=True,
        notes_for_consultant="Please review medication options.",
        actor=actor,
    )
    ConsultationService(db_session).record_consultation(
        patient_id=patient.patient_id,
        consultation_date=date(2026, 2, 8),
        actor=actor,
    )

    flag_entries = [
        e
        for e in entries(db_session, patient.patient_id)
        if e.action in (AuditAction.FLAG_SET, AuditAction.FLAG_CLEARED)
    ]
    assert [e.action for e in flag_entries] == [AuditAction.FLAG_CLEARED, AuditAction.FLAG_SET]
    assert all(e.field == "needs_psychiatric_review" for e in flag_entries)
    assert flag_entries[1].old_value == "false" and flag_entries[1].new_value == "true"
    assert flag_entries[0].old_value == "true" and flag_entries[0].new_value == "false"
    # The trail says WHY, not just what.
    assert "discuss-with-consultant checked" in flag_entries[1].context
    assert "consultation" in flag_entries[0].context


def test_every_score_is_audited(db_session, actor):
    patient = make_patient(db_session, "MRN-AUDIT-3")
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id,
        start_date=date(2026, 1, 1),
        primary_diagnosis=ConditionType.DEPRESSION,
        actor=actor,
    )
    ContactService(db_session).record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 5),
        scores=[
            {"measure_type": MeasureType.PHQ9, "score_value": 18},
            {"measure_type": MeasureType.GAD7, "score_value": 12},
        ],
        actor=actor,
    )

    score_entries = [
        e for e in entries(db_session, patient.patient_id) if e.action == AuditAction.SCORE_RECORDED
    ]
    assert len(score_entries) == 2
    assert sorted((e.field, e.new_value) for e in score_entries) == [
        ("GAD7", "12"),
        ("PHQ9", "18"),
    ]
    assert all(e.entity_type == "symptom_score" for e in score_entries)
    assert all("initial_assessment contact" in e.context for e in score_entries)


# --- episode lifecycle ------------------------------------------------------


def test_episode_open_and_close_are_audited(db_session, actor):
    patient = make_patient(db_session, "MRN-AUDIT-4")
    service = EpisodeService(db_session)
    episode = service.create_episode(
        patient_id=patient.patient_id,
        start_date=date(2026, 1, 1),
        primary_diagnosis=ConditionType.ANXIETY,
        actor=actor,
    )
    service.update_episode(
        episode.episode_id, actor=actor, end_date=date(2026, 6, 1), end_reason="achieved_goals"
    )

    recorded = actions(db_session, patient.patient_id)
    assert AuditAction.EPISODE_OPENED in recorded
    assert AuditAction.EPISODE_CLOSED in recorded
    opened = next(
        e for e in entries(db_session, patient.patient_id) if e.action == AuditAction.EPISODE_OPENED
    )
    assert "primary=anxiety" in opened.context
    closed = next(
        e for e in entries(db_session, patient.patient_id) if e.action == AuditAction.EPISODE_CLOSED
    )
    assert closed.new_value == "2026-06-01"
    assert "achieved_goals" in closed.context
    # Closing cascades a status change, which is audited separately.
    status_entry = next(
        e
        for e in entries(db_session, patient.patient_id)
        if e.action == AuditAction.STATUS_CHANGED and e.new_value == "deactivated"
    )
    assert "cascade from closing" in status_entry.context


# --- the log is append-only and readable -----------------------------------


def test_audit_entries_are_ordered_newest_first(db_session, actor):
    patient = make_patient(db_session, "MRN-AUDIT-5")
    service = EpisodeService(db_session)
    episode = service.create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 1), actor=actor
    )
    service.transition_status(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        status=TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN,
        status_changed_date=date(2026, 3, 1),
        actor=actor,
    )
    rows = entries(db_session, patient.patient_id)
    ids = [e.audit_log_id for e in rows]
    assert ids == sorted(ids, reverse=True)


def test_a_patients_trail_excludes_other_patients(db_session, actor):
    first = make_patient(db_session, "MRN-AUDIT-6")
    second = make_patient(db_session, "MRN-AUDIT-7")
    service = EpisodeService(db_session)
    service.create_episode(patient_id=first.patient_id, start_date=date(2026, 1, 1), actor=actor)
    service.create_episode(patient_id=second.patient_id, start_date=date(2026, 1, 1), actor=actor)

    assert all(e.patient_id == first.patient_id for e in entries(db_session, first.patient_id))
    assert len(entries(db_session, second.patient_id)) >= 1


def test_writes_without_an_authenticated_provider_still_log_what_and_when(db_session):
    """
    Scripts talk to the service layer directly with no provider. The actor is
    unknown, but the change must still be recorded — a partial trail beats a
    missing one.
    """
    patient = make_patient(db_session, "MRN-AUDIT-8")
    EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 1)
    )
    rows = entries(db_session, patient.patient_id)
    assert len(rows) >= 1
    assert all(e.actor_provider_id is None and e.actor_label is None for e in rows)
    assert all(e.occurred_at is not None and e.action is not None for e in rows)


# --- the guard: routes must supply the actor -------------------------------


def test_routes_record_the_authenticated_actor(db_session, actor, client):
    """
    Drives the real write routes over HTTP and asserts every resulting audit
    entry names the signed-in provider. This is what catches a new or edited
    route that forgets to bind Depends(get_current_provider) and pass it on.
    """
    token = client.post(
        "/auth/login", json={"email": ACTOR_EMAIL, "password": ACTOR_PASSWORD}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patient = make_patient(db_session, "MRN-AUDIT-HTTP")
    episode = client.post(
        "/episodes",
        json={
            "patient_id": patient.patient_id,
            "start_date": "2026-01-01",
            "primary_diagnosis": "depression",
        },
        headers=headers,
    ).json()

    client.post(
        "/contacts",
        json={
            "patient_id": patient.patient_id,
            "episode_id": episode["episode_id"],
            "contact_type": "initial_assessment",
            "contact_date": "2026-01-05",
            "discuss_with_psychiatric_consultant": True,
            "notes_for_consultant": "Review please.",
            "scores": [{"measure_type": "PHQ9", "score_value": 19}],
        },
        headers=headers,
    )
    client.post(
        "/consultations",
        json={
            "patient_id": patient.patient_id,
            "consultation_date": "2026-01-12",
            "duration_minutes": 20,
        },
        headers=headers,
    )
    client.patch(
        f"/patients/{patient.patient_id}", json={"safety_risk": True}, headers=headers
    )
    client.patch(
        f"/episodes/{episode['episode_id']}",
        json={"end_date": "2026-06-01", "end_reason": "achieved_goals"},
        headers=headers,
    )

    rows = entries(db_session, patient.patient_id)
    recorded = {e.action for e in rows}
    assert {
        AuditAction.EPISODE_OPENED,
        AuditAction.STATUS_CHANGED,
        AuditAction.SCORE_RECORDED,
        AuditAction.FLAG_SET,
        AuditAction.FLAG_CLEARED,
        AuditAction.EPISODE_CLOSED,
    } <= recorded

    anonymous = [e for e in rows if e.actor_provider_id is None]
    assert not anonymous, (
        "every audit entry from an HTTP route must name the authenticated provider; "
        f"{len(anonymous)} did not: {[(e.action.value, e.field) for e in anonymous]}"
    )
    assert all(e.actor_label == "Dr. Audit Actor" for e in rows)

    # The safety flag — the one the caseload list paints red — is attributable.
    safety = next(e for e in rows if e.field == "safety_risk")
    assert safety.action == AuditAction.FLAG_SET
    assert safety.old_value == "false" and safety.new_value == "true"
    assert safety.actor_provider_id == actor.provider_id


def test_audit_log_read_endpoint(db_session, actor, client):
    token = client.post(
        "/auth/login", json={"email": ACTOR_EMAIL, "password": ACTOR_PASSWORD}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patient = make_patient(db_session, "MRN-AUDIT-READ")
    EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 1), actor=actor
    )

    response = client.get("/audit-log", params={"patient_id": patient.patient_id}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert body[0]["actor_label"] == "Dr. Audit Actor"
    assert body[0]["patient_id"] == patient.patient_id

    assert client.get("/audit-log").status_code == 401  # protected like every other router


def test_audit_log_has_no_write_or_delete_routes(client):
    """
    The table is append-only; only AuditService writes to it. 404 (no such
    path is routed at all) and 405 (routed but the method isn't allowed) are
    both proof there's no write route — 404 is the stronger of the two.
    """
    assert client.post("/audit-log", json={}).status_code in (404, 405)
    assert client.delete("/audit-log/1").status_code in (404, 405)
    assert client.patch("/audit-log/1", json={}).status_code in (404, 405)
