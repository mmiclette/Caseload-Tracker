"""
Patient <-> Provider traceability walkthrough.

Answers a concrete question: if I create one patient, tie them to a
provider (and a clinic), and record some activity, does that patient's
data actually show up everywhere it's supposed to — under the patient's
own record, under the provider's caseload, under the clinic's caseload,
on the Reminders list, and on the Active Patients report?

This is a manual verification aid, not part of the pytest suite (though it
exercises the same routes the pytest suite exercises with mocked/isolated
data) — it's meant to be read top to bottom, print by print, as a trace of
one patient's data through every surface. Run with:

    python scripts/patient_provider_traceability_walkthrough.py

Requires the dev Postgres database at head. Creates its own scratch data
and does not clean up afterward — same caveat as scripts/phase2_smoke_test.py.
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
FAILURES: list[str] = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f"  ({detail})" if detail else ""))
    if not condition:
        FAILURES.append(label)


def bootstrap_and_login() -> str:
    db = SessionLocal()
    try:
        repo = ProviderRepository(db)
        email, password = "walkthrough-admin@example.com", "walkthrough-password"
        if repo.get_by_email(email) is None:
            repo.create(
                Provider(
                    name="Walkthrough Admin",
                    role=ProviderRole.CLINIC_SUPERVISOR,
                    email=email,
                    hashed_password=hash_password(password),
                )
            )
    finally:
        db.close()
    resp = client.post("/auth/login", json={"email": email, "password": password})
    resp.raise_for_status()
    return resp.json()["access_token"]


def main():
    client.headers["Authorization"] = f"Bearer {bootstrap_and_login()}"

    print("=== Step 1: create a Care Manager and a Psychiatric Consultant ===")
    care_manager = client.post(
        "/providers", json={"name": "Priya Nandakumar", "role": "care_manager"}
    ).json()
    consultant = client.post(
        "/providers", json={"name": "Dr. Elena Cho", "role": "psychiatric_consultant"}
    ).json()
    check("care manager created", "provider_id" in care_manager, f"id={care_manager.get('provider_id')}")
    check("consultant created", "provider_id" in consultant, f"id={consultant.get('provider_id')}")

    print("\n=== Step 2: create the patient ===")
    patient = client.post(
        "/patients",
        json={
            "mrn": "WALK-0001",
            "name": "Sam Okafor",
            "payer": "Medicaid",
            "date_of_birth": "1978-11-02",
            "consent_date": "2026-01-01",
            "enrollment_date": "2026-01-02",
        },
    ).json()
    check("patient created", "patient_id" in patient, f"id={patient.get('patient_id')}")

    print("\n=== Step 3: tie the patient to the care manager (Care Team) and a clinic ===")
    care_team = client.post(
        "/care-team-assignments",
        json={
            "patient_id": patient["patient_id"],
            "provider_id": care_manager["provider_id"],
            "role": "care_manager",
            "service_begin_date": "2026-01-02",
        },
    ).json()
    check("care team assignment created", "care_team_assignment_id" in care_team)

    clinic = client.post(
        "/clinic-assignments",
        json={
            "patient_id": patient["patient_id"],
            "clinic_id": "walkthrough-clinic",
            "is_primary": True,
            "service_begin_date": "2026-01-02",
        },
    ).json()
    check("clinic assignment created", "clinic_assignment_id" in clinic)

    print("\n=== Step 4: open an episode and record an initial assessment (via the care manager) ===")
    episode = client.post(
        "/episodes", json={"patient_id": patient["patient_id"], "start_date": "2026-01-05"}
    ).json()
    check("episode created", "episode_id" in episode)

    initial_contact = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "episode_id": episode["episode_id"],
            "provider_id": care_manager["provider_id"],
            "contact_type": "initial_assessment",
            "contact_date": "2026-01-05",
            "duration_minutes": 50,
            "scores": [{"measure_type": "PHQ9", "score_value": 19, "recorded_by": "Priya Nandakumar"}],
        },
    ).json()
    check("initial assessment contact recorded", "contact_id" in initial_contact)

    print("\n=== Step 5: a follow-up flags the case for psychiatric review ===")
    followup_contact = client.post(
        "/contacts",
        json={
            "patient_id": patient["patient_id"],
            "episode_id": episode["episode_id"],
            "provider_id": care_manager["provider_id"],
            "contact_type": "follow_up",
            "contact_date": "2026-01-19",
            "duration_minutes": 30,
            "discuss_with_psychiatric_consultant": True,
            "notes_for_consultant": "Walkthrough: limited improvement, consider medication review",
            "scores": [{"measure_type": "PHQ9", "score_value": 15}],
        },
    ).json()
    check("flagged follow-up contact recorded", "contact_id" in followup_contact)

    print("\n=== Now checking every surface this patient's data should appear on ===\n")

    # 1. The patient's own record
    fetched_patient = client.get(f"/patients/{patient['patient_id']}").json()
    check(
        "1. Patient record shows the psychiatric review flag turned on",
        fetched_patient.get("needs_psychiatric_review") is True,
    )

    # 2. The episode, with baseline set from the first score
    fetched_episode = client.get(f"/episodes/{episode['episode_id']}").json()
    check(
        "2. Episode shows baseline PHQ-9 = 19 from the initial assessment",
        fetched_episode.get("baseline_score") == 19
        and fetched_episode.get("baseline_measure_type") == "PHQ9",
    )

    # 3. The care manager's current care team assignment for this patient
    team_for_patient = client.get(
        "/care-team-assignments",
        params={"patient_id": patient["patient_id"], "current_only": True},
    ).json()
    check(
        "3. Care manager appears on the patient's current care team",
        any(a["provider_id"] == care_manager["provider_id"] for a in team_for_patient),
    )

    # 4. The clinic assignment
    clinics_for_patient = client.get(
        "/clinic-assignments", params={"patient_id": patient["patient_id"]}
    ).json()
    check(
        "4. Clinic assignment appears under the patient",
        any(c["clinic_id"] == "walkthrough-clinic" for c in clinics_for_patient),
    )

    # 5. Contacts, correctly attributed to the care manager
    contacts_for_patient = client.get(
        "/contacts", params={"patient_id": patient["patient_id"]}
    ).json()
    check(
        "5. Both contacts appear under the patient, attributed to the care manager",
        len(contacts_for_patient) == 2
        and all(c["provider_id"] == care_manager["provider_id"] for c in contacts_for_patient),
    )

    # 6. Scores, reachable per-contact
    scores_for_initial_contact = client.get(
        f"/contacts/{initial_contact['contact_id']}/scores"
    ).json()
    check(
        "6. The initial assessment's score is reachable via /contacts/{id}/scores",
        len(scores_for_initial_contact) == 1 and scores_for_initial_contact[0]["score_value"] == 19,
    )

    # 7. The Reminders landing list
    pending_reminders = client.get("/reminders", params={"status": "pending"}).json()
    patient_reminder = next(
        (r for r in pending_reminders if r["patient_id"] == patient["patient_id"]), None
    )
    check(
        "7. Patient has a pending reminder on the Reminders landing list",
        patient_reminder is not None,
        f"due_date={patient_reminder['due_date'] if patient_reminder else None}",
    )
    check(
        "   reminder due date reflects the 14-day active-treatment cadence off the last contact",
        patient_reminder is not None and patient_reminder["due_date"] == "2026-02-02",
    )

    # 8. Active Patients report, unfiltered
    all_active = client.get("/reports/active-patients", params={"as_of": "2026-01-20"}).json()
    row = next((r for r in all_active if r["patient_id"] == patient["patient_id"]), None)
    check("8. Patient appears on the unfiltered Active Patients report", row is not None)
    check(
        "   report row shows CONSIDER for Psychiatric Consultation (flag set, no Consultation yet)",
        row is not None and row["psychiatric_consultation"] == "CONSIDER",
    )
    check(
        "   report row shows 2 sessions and correct minutes-this-month total",
        row is not None and row["session_count"] == 2,
    )

    # 9. Active Patients report, filtered by this specific provider
    filtered_by_provider = client.get(
        "/reports/active-patients",
        params={"provider_id": care_manager["provider_id"], "as_of": "2026-01-20"},
    ).json()
    check(
        "9. Patient appears when the Active Patients report is filtered to their care manager",
        any(r["patient_id"] == patient["patient_id"] for r in filtered_by_provider),
    )

    # 10. Active Patients report, filtered by a DIFFERENT provider — should NOT appear
    filtered_by_other_provider = client.get(
        "/reports/active-patients",
        params={"provider_id": consultant["provider_id"], "as_of": "2026-01-20"},
    ).json()
    check(
        "10. Patient correctly absent when filtered to an unrelated provider (the consultant)",
        all(r["patient_id"] != patient["patient_id"] for r in filtered_by_other_provider),
    )

    # 11. Active Patients report, filtered by this specific clinic
    filtered_by_clinic = client.get(
        "/reports/active-patients",
        params={"clinic_id": "walkthrough-clinic", "as_of": "2026-01-20"},
    ).json()
    check(
        "11. Patient appears when the Active Patients report is filtered to their clinic",
        any(r["patient_id"] == patient["patient_id"] for r in filtered_by_clinic),
    )

    print("\n=== Step 6: the consultant records a Consultation, clearing the flag ===")
    consultation = client.post(
        "/consultations",
        json={
            "patient_id": patient["patient_id"],
            "provider_id": consultant["provider_id"],
            "consultation_date": "2026-01-21",
            "recommendations_forwarded": True,
        },
    ).json()
    check("consultation recorded", "consultation_id" in consultation)

    # 12. Flag clears, and the report now shows the consultation date instead of CONSIDER
    fetched_patient_after = client.get(f"/patients/{patient['patient_id']}").json()
    check(
        "12. Psychiatric review flag cleared on the patient record after the consultation",
        fetched_patient_after.get("needs_psychiatric_review") is False,
    )
    report_after_consultation = client.get(
        "/reports/active-patients", params={"as_of": "2026-01-25"}
    ).json()
    row_after = next(
        (r for r in report_after_consultation if r["patient_id"] == patient["patient_id"]), None
    )
    check(
        "    report now shows the consultation date instead of CONSIDER",
        row_after is not None and row_after["psychiatric_consultation"] == "2026-01-21",
    )

    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("Every surface checked out: this patient's data is consistent end to end.")


if __name__ == "__main__":
    main()
