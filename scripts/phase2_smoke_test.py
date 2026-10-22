"""
Phase 2 + Phase 3 end-to-end smoke test.

Exercises the full HTTP stack (FastAPI TestClient -> routes -> services ->
repositories -> real Postgres) against the dev database, the same way the
Phase 1 and CTMS-fold-in smoke tests did. Run with:

    python scripts/phase2_smoke_test.py

Requires the dev Postgres database to be migrated to head (alembic upgrade
head) and reachable via DATABASE_URL / the default in app.core.config.
This script creates its own patient/provider rows and does not delete them
afterward — run it against a scratch/dev database, not one you care about.

Phase 3 protected every route behind Provider auth (see app/core/deps.py),
so this script bootstraps its own admin account directly through the
repository layer (mirroring scripts/create_admin_provider.py — the API
itself can't create the first account, since creating one now requires
already being logged in) and logs in before touching anything else.
"""

import sys

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import SessionLocal
from app.main import app
from app.models.enums import ProviderRole
from app.models.provider import Provider
from app.repositories.provider import ProviderRepository

client = TestClient(app)


def _bootstrap_and_login() -> str:
    db = SessionLocal()
    try:
        repo = ProviderRepository(db)
        email = "smoke-admin@example.com"
        password = "smoke-test-password"
        existing = repo.get_by_email(email)
        if existing is None:
            repo.create(
                Provider(
                    name="Smoke Admin",
                    role=ProviderRole.CLINIC_SUPERVISOR,
                    email=email,
                    hashed_password=hash_password(password),
                )
            )
    finally:
        db.close()

    login = client.post("/auth/login", json={"email": email, "password": password})
    login.raise_for_status()
    return login.json()["access_token"]


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        FAILURES.append(label)


FAILURES: list[str] = []


def main():
    token = _bootstrap_and_login()
    client.headers["Authorization"] = f"Bearer {token}"
    check("bootstrap admin login issued a token", bool(token))

    # --- Provider ---
    care_manager = client.post(
        "/providers", json={"name": "Smoke CM", "role": "care_manager"}
    ).json()
    consultant = client.post(
        "/providers", json={"name": "Smoke Consultant", "role": "psychiatric_consultant"}
    ).json()
    check("create provider (care manager)", "provider_id" in care_manager)
    check("create provider (consultant)", "provider_id" in consultant)

    role_filtered = client.get("/providers", params={"role": "care_manager"}).json()
    check(
        "list providers filtered by role",
        any(p["provider_id"] == care_manager["provider_id"] for p in role_filtered),
    )

    # --- Patient ---
    patient = client.post(
        "/patients",
        json={
            "mrn": "SMOKE-P2-001",
            "name": "Phase 2 Smoke Patient",
            "payer": "Medicaid",
            "date_of_birth": "1990-06-15",
            "consent_date": "2026-01-01",
            "enrollment_date": "2026-01-02",
        },
    ).json()
    check("create patient", "patient_id" in patient)
    check("patient has no clinic_id field", "clinic_id" not in patient)
    check("patient age is computed", patient.get("age") is not None)

    # --- Episode ---
    episode = client.post(
        "/episodes", json={"patient_id": patient["patient_id"], "start_date": "2026-02-01"}
    ).json()
    check("create episode", "episode_id" in episode)

    status_after_create = client.get(f"/episodes/{episode['episode_id']}/status/history").json()
    check(
        "episode creation sets active_treatment status",
        status_after_create and status_after_create[0]["status"] == "active_treatment",
    )

    # --- Care Team Assignment ---
    assignment = client.post(
        "/care-team-assignments",
        json={
            "patient_id": patient["patient_id"],
            "provider_id": care_manager["provider_id"],
            "role": "care_manager",
            "service_begin_date": "2026-01-02",
        },
    ).json()
    check("create care team assignment", "care_team_assignment_id" in assignment)
    current_team = client.get(
        "/care-team-assignments", params={"patient_id": patient["patient_id"], "current_only": True}
    ).json()
    check("current care team assignment listed", len(current_team) == 1)

    # --- Clinic Assignment ---
    clinic_assignment = client.post(
        "/clinic-assignments",
        json={
            "patient_id": patient["patient_id"],
            "clinic_id": "smoke-clinic-a",
            "is_primary": True,
            "service_begin_date": "2026-01-02",
        },
    ).json()
    check("create clinic assignment", "clinic_assignment_id" in clinic_assignment)

    # --- Contact with scores: baseline cascade ---
    contact_1 = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "episode_id": episode["episode_id"],
            "provider_id": care_manager["provider_id"],
            "contact_type": "initial_assessment",
            "contact_date": "2026-02-01",
            "location": "virtual",
            "duration_minutes": 45,
            "scores": [{"measure_type": "PHQ9", "score_value": 18, "recorded_by": "Smoke CM"}],
        },
    ).json()
    check("record initial contact with score", "contact_id" in contact_1)

    episode_after_baseline = client.get(f"/episodes/{episode['episode_id']}").json()
    check(
        "baseline set from first contact's score",
        episode_after_baseline["baseline_score"] == 18
        and episode_after_baseline["baseline_measure_type"] == "PHQ9",
    )

    contact_scores = client.get(f"/contacts/{contact_1['contact_id']}/scores").json()
    check("contact scores retrievable via /contacts/{id}/scores", len(contact_scores) == 1)

    # --- Backdated contact: baseline recompute ---
    contact_backdated = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "episode_id": episode["episode_id"],
            "contact_type": "follow_up",
            "contact_date": "2026-01-20",
            "scores": [{"measure_type": "PHQ9", "score_value": 22}],
        },
    ).json()
    check("record backdated contact", "contact_id" in contact_backdated)
    episode_after_backdate = client.get(f"/episodes/{episode['episode_id']}").json()
    check(
        "baseline recomputes to the earlier backdated score",
        episode_after_backdate["baseline_score"] == 22
        and episode_after_backdate["baseline_date"] == "2026-01-20",
    )

    # --- Discuss with consultant: flag cascade ---
    contact_flagged = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "episode_id": episode["episode_id"],
            "contact_type": "follow_up",
            "contact_date": "2026-02-15",
            "discuss_with_psychiatric_consultant": True,
            "notes_for_consultant": "Smoke test: possible medication change",
        },
    ).json()
    check("record contact flagged for consultant", "contact_id" in contact_flagged)
    patient_after_flag = client.get(f"/patients/{patient['patient_id']}").json()
    check("needs_psychiatric_review flag turned on", patient_after_flag["needs_psychiatric_review"] is True)

    # --- Contact attempt: attempt_number sequencing ---
    attempt_1 = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "contact_type": "contact_attempt",
            "contact_date": "2026-03-01",
        },
    ).json()
    attempt_2 = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "contact_type": "contact_attempt",
            "contact_date": "2026-03-08",
        },
    ).json()
    check("first contact attempt is attempt #1", attempt_1.get("attempt_number") == 1)
    check("second consecutive contact attempt is attempt #2", attempt_2.get("attempt_number") == 2)

    # --- Contact attempt cannot carry scores (422) ---
    bad_attempt = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "contact_type": "contact_attempt",
            "contact_date": "2026-03-15",
            "scores": [{"measure_type": "PHQ9", "score_value": 5}],
        },
    )
    check("contact_attempt with scores rejected as 422", bad_attempt.status_code == 422)

    # --- Scores require episode_id (422) ---
    bad_scores = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "contact_type": "follow_up",
            "contact_date": "2026-03-15",
            "scores": [{"measure_type": "PHQ9", "score_value": 5}],
        },
    )
    check("scores without episode_id rejected as 422", bad_scores.status_code == 422)

    # --- RPP contact: treatment status cascade ---
    rpp_contact = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "episode_id": episode["episode_id"],
            "contact_type": "relapse_prevention_plan",
            "contact_date": "2026-04-01",
            "scores": [{"measure_type": "PHQ9", "score_value": 3}],
        },
    ).json()
    check("record RPP contact", "contact_id" in rpp_contact)
    status_history = client.get(f"/episodes/{episode['episode_id']}/status/history").json()
    check(
        "RPP contact cascades to relapse_prevention_plan status",
        status_history[-1]["status"] == "relapse_prevention_plan",
    )

    # --- Consultation: clears the flag ---
    consultation = client.post(
        "/consultations",
        json={
            "patient_id": patient["patient_id"],
            "provider_id": consultant["provider_id"],
            "consultation_date": "2026-04-05",
            "recommendations_forwarded": True,
        },
    ).json()
    check("record consultation", "consultation_id" in consultation)
    patient_after_consultation = client.get(f"/patients/{patient['patient_id']}").json()
    check(
        "consultation clears needs_psychiatric_review flag",
        patient_after_consultation["needs_psychiatric_review"] is False,
    )

    # --- Consultation with flagged_for_next_review re-sets the flag ---
    consultation_2 = client.post(
        "/consultations",
        json={
            "patient_id": patient["patient_id"],
            "provider_id": consultant["provider_id"],
            "consultation_date": "2026-05-05",
            "flagged_for_next_review": True,
            "flag_reason": "Smoke test: check again next review cycle",
        },
    ).json()
    check("record consultation with flagged_for_next_review", "consultation_id" in consultation_2)
    patient_after_second_consultation = client.get(f"/patients/{patient['patient_id']}").json()
    check(
        "flagged_for_next_review re-sets needs_psychiatric_review",
        patient_after_second_consultation["needs_psychiatric_review"] is True,
    )

    # --- Reminder cascade: appointment reminder reflects latest cadence ---
    reminders_for_patient = client.get(
        "/reminders", params={"patient_id": patient["patient_id"]}
    ).json()
    pending_reminder = next((r for r in reminders_for_patient if r["status"] == "pending"), None)
    check("pending appointment reminder exists after RPP contact", pending_reminder is not None)
    check(
        "reminder due date reflects RPP cadence (28 days after last contact)",
        pending_reminder is not None and pending_reminder["due_date"] == "2026-04-29",
    )

    # --- Active Patients report ---
    report_rows = client.get("/reports/active-patients", params={"as_of": "2026-04-15"}).json()
    report_row = next((r for r in report_rows if r["patient_id"] == patient["patient_id"]), None)
    check("patient appears on Active Patients report while episode is open", report_row is not None)
    check(
        "Active Patients report reflects RPP contact date",
        report_row is not None and report_row["relapse_prevention_plan_date"] == "2026-04-01",
    )

    # --- Episode close: deactivation cascade ---
    close_response = client.patch(
        f"/episodes/{episode['episode_id']}",
        json={"end_date": "2026-06-01", "end_reason": "achieved_goals"},
    ).json()
    check("close episode", close_response.get("end_date") == "2026-06-01")
    final_status_history = client.get(f"/episodes/{episode['episode_id']}/status/history").json()
    check(
        "closing episode cascades to deactivated status",
        final_status_history[-1]["status"] == "deactivated",
    )

    # --- Reminder cascade: closing the episode dismisses the pending reminder ---
    reminders_after_close = client.get(
        "/reminders", params={"patient_id": patient["patient_id"]}
    ).json()
    check(
        "closing episode dismisses the pending appointment reminder",
        all(r["status"] != "pending" for r in reminders_after_close),
    )

    # --- Active Patients report excludes deactivated patients ---
    report_rows_after_close = client.get(
        "/reports/active-patients", params={"as_of": "2026-06-15"}
    ).json()
    check(
        "deactivated patient excluded from Active Patients report",
        all(r["patient_id"] != patient["patient_id"] for r in report_rows_after_close),
    )

    # --- Referral: creates both the Referral row and its follow-up reminder ---
    referral = client.post(
        "/referrals",
        json={
            "patient_id": patient["patient_id"],
            "referral_date": "2026-05-01",
            "referred_to": "Smoke Test Housing Program",
        },
    ).json()
    check("referral recorded", "referral_id" in referral)
    referral_reminders = client.get(
        "/reminders", params={"patient_id": patient["patient_id"], "status": "pending"}
    ).json()
    referral_reminder = next(
        (r for r in referral_reminders if r.get("referral_id") == referral.get("referral_id")), None
    )
    check(
        "referral reminder due 4 weeks after referral_date",
        referral_reminder is not None and referral_reminder["due_date"] == "2026-05-29",
    )

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All smoke test checks passed.")


if __name__ == "__main__":
    main()
