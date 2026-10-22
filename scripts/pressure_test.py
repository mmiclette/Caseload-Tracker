"""
Full-platform pressure test (2026-08).

Simulates a CoCM program running February through July 2026 — six patients,
three providers, two clinics, ~30 encounters — entirely through the real
HTTP API (FastAPI TestClient -> routes -> services -> repositories -> real
Postgres), then asserts every downstream surface:

  1. Patient intake round-trips (demographics, eligibility, consent).
  2. Encounter notes and psychiatric consultation notes persist and are
     retrievable later (Phase 8 fields).
  3. Patient information populates the Clinical Dashboard and Active
     Patients report (scores, flags, meds, profile entries, trends).
  4. Population-level metrics split correctly by primary condition
     (depression vs anxiety vs pediatric/unscored).
  5. Patients can be added and removed; a removed patient stops counting
     toward every month after their removal — Quality Metrics months are
     strictly "the caseload we worked with during that calendar month."

Run against a DEDICATED scratch database (the script refuses otherwise):

    createdb/ALEMBIC:  DATABASE_URL=...cocm_registry_pressure alembic upgrade head
    RUN:               DATABASE_URL=...cocm_registry_pressure python scripts/pressure_test.py
"""

import os
import sys

if "pressure" not in os.environ.get("DATABASE_URL", ""):
    sys.exit("Refusing to run: point DATABASE_URL at a dedicated *pressure* database first.")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import ProviderRole  # noqa: E402
from app.models.provider import Provider  # noqa: E402
from app.repositories.provider import ProviderRepository  # noqa: E402

client = TestClient(app)

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def section(title):
    print(f"\n=== {title} ===")


def _bootstrap_and_login() -> dict:
    db = SessionLocal()
    try:
        repo = ProviderRepository(db)
        email = "pressure-admin@example.com"
        if repo.get_by_email(email) is None:
            repo.create(
                Provider(
                    name="Pressure Admin",
                    role=ProviderRole.CLINIC_SUPERVISOR,
                    email=email,
                    hashed_password=hash_password("pressure-test-password"),
                )
            )
    finally:
        db.close()
    login = client.post(
        "/auth/login", json={"email": email, "password": "pressure-test-password"}
    )
    login.raise_for_status()
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


H = _bootstrap_and_login()


def post(path, json):
    r = client.post(path, json=json, headers=H)
    assert r.status_code in (200, 201), f"POST {path} -> {r.status_code}: {r.text}"
    return r.json()


def patch(path, json):
    r = client.patch(path, json=json, headers=H)
    assert r.status_code == 200, f"PATCH {path} -> {r.status_code}: {r.text}"
    return r.json()


def get(path, **params):
    r = client.get(path, params=params, headers=H)
    assert r.status_code == 200, f"GET {path} -> {r.status_code}: {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# Cast
# ---------------------------------------------------------------------------
section("Setup: providers and helpers")

dana = post("/providers", {"name": "Dana Whitfield", "role": "care_manager",
                           "email": "dana@example.com", "password": "x-dana-pass"})
ramon = post("/providers", {"name": "Ramon Ortiz", "role": "psychiatric_consultant"})
lena = post("/providers", {"name": "Lena Fischer", "role": "primary_care_provider"})
check("three providers created", dana["provider_id"] and ramon["provider_id"] and lena["provider_id"])


def intake(mrn, name, dob, enroll, clinic, primary, secondary=None, payer="Medicaid",
           race=None, eligibility=None):
    """The full patient-intake flow: demographics -> episode with diagnoses
    -> care team -> clinic. Returns (patient, episode)."""
    patient = post("/patients", {
        "mrn": mrn, "name": name, "payer": payer, "date_of_birth": dob,
        "consent_date": enroll, "enrollment_date": enroll,
        "race_ethnicity": race, "program_eligibility": eligibility,
    })
    episode = post("/episodes", {
        "patient_id": patient["patient_id"], "start_date": enroll,
        "primary_diagnosis": primary, "secondary_diagnosis": secondary,
    })
    post("/care-team-assignments", {
        "patient_id": patient["patient_id"], "provider_id": dana["provider_id"],
        "role": "care_manager", "service_begin_date": enroll,
    })
    post("/clinic-assignments", {
        "patient_id": patient["patient_id"], "clinic_id": clinic,
        "is_primary": True, "service_begin_date": enroll,
    })
    return patient, episode


def visit(patient, episode, ctype, cdate, minutes, scores=None, notes=None, **kw):
    return post("/contacts", {
        "patient_id": patient["patient_id"], "episode_id": episode["episode_id"],
        "provider_id": dana["provider_id"], "contact_type": ctype,
        "contact_date": cdate, "duration_minutes": minutes,
        "location": "virtual", "notes": notes,
        "scores": [{"measure_type": m, "score_value": v} for m, v in (scores or [])],
        **kw,
    })


# ---------------------------------------------------------------------------
# Six patients, February–July 2026
# ---------------------------------------------------------------------------
section("Data entry: six patients across six months")

# P1 Alice — depression primary; responds, remits, moves to RPP. Meds + profile.
p1, e1 = intake("PT-1001", "Alice Nguyen", "1988-04-12", "2026-02-02", "northside",
                "depression", race=["Asian"], eligibility={"medicaid_plan": "Standard"})
post("/care-team-assignments", {"patient_id": p1["patient_id"], "provider_id": ramon["provider_id"],
                                "role": "psychiatric_consultant", "service_begin_date": "2026-02-02"})
visit(p1, e1, "initial_assessment", "2026-02-03", 45, [("PHQ9", 18)],
      notes="Intake encounter. Pt reports low mood, anhedonia x3 months. Started BA plan.")
visit(p1, e1, "follow_up", "2026-03-03", 30, [("PHQ9", 12)], notes="BA homework partially done.")
visit(p1, e1, "follow_up", "2026-04-07", 30, [("PHQ9", 8)], notes="Clear response. Continue plan.")
visit(p1, e1, "follow_up", "2026-05-05", 30, [("PHQ9", 4)], notes="Remission range. Discussed RPP.")
visit(p1, e1, "relapse_prevention_plan", "2026-06-02", 25, [("PHQ9", 3)],
      notes="RPP completed and signed.",
      other_treatments="Weekly counseling at Community Counseling Collective",
      personal_warning_signs="Sleeping past noon; skipping morning walks; avoiding calls",
      stress_reduction_plan="Daily 20-minute walk; Saturday hiking group",
      additional_comments="Copy of plan given to patient and PCP.",
      medications_confirmation="confirmed_with_patient")
p1_med = post("/medications", {"patient_id": p1["patient_id"], "medication_key": "sertraline",
                               "dose": "50 mg", "frequency": "daily", "recorded_by": "Dana Whitfield"})
post("/profile-entries", {"patient_id": p1["patient_id"], "section": "safety_and_risk",
                          "sub_field": "safety_plan", "value": "Completed, copy given to patient",
                          "recorded_date": "2026-02-03", "context": "Done at intake"})
post("/profile-entries", {"patient_id": p1["patient_id"], "section": "social_environmental",
                          "sub_field": "living_situation", "value": "Lives with partner, stable housing",
                          "recorded_date": "2026-02-03"})

# P2 Ben — anxiety primary + depression secondary. Dual scales every visit.
# PHQ-9 listed FIRST at intake to exercise the baseline re-anchor rule.
p2, e2 = intake("PT-1002", "Ben Okafor", "1979-11-30", "2026-02-09", "northside",
                "anxiety", secondary="depression", payer="Commercial")
visit(p2, e2, "initial_assessment", "2026-02-09", 50, [("PHQ9", 15), ("GAD7", 16)],
      notes="Intake encounter. Panic sx at work; PHQ elevated but anxiety is primary driver.")
visit(p2, e2, "follow_up", "2026-03-09", 30, [("GAD7", 11), ("PHQ9", 10)], notes="CBT session 2.")
post("/referrals", {"patient_id": p2["patient_id"], "referred_by_provider_id": dana["provider_id"],
                    "referred_to": "Community Counseling Collective",
                    "referral_date": "2026-03-09", "reason": "Weekly individual therapy"})
visit(p2, e2, "follow_up", "2026-04-13", 30, [("GAD7", 7), ("PHQ9", 8)], notes="CBT session 3.")
visit(p2, e2, "follow_up", "2026-05-11", 30, [("GAD7", 4), ("PHQ9", 6)], notes="Sustained gains.")
post("/medications", {"patient_id": p2["patient_id"], "medication_name": "Metformin",
                      "dose": "500 mg", "frequency": "twice daily"})

# P3 Carla — anxiety primary, NOT improving; yellow-flag -> consultation cycle.
p3, e3 = intake("PT-1003", "Carla Reyes", "1991-07-08", "2026-02-16", "westend", "anxiety")
post("/care-team-assignments", {"patient_id": p3["patient_id"], "provider_id": ramon["provider_id"],
                                "role": "psychiatric_consultant", "service_begin_date": "2026-02-16"})
visit(p3, e3, "initial_assessment", "2026-02-17", 45, [("GAD7", 17)], notes="Intake encounter.")
visit(p3, e3, "follow_up", "2026-03-17", 30, [("GAD7", 16)],
      notes="Minimal change after 4 weeks.",
      discuss_with_psychiatric_consultant=True,
      notes_for_consultant="No improvement after 4 weeks of CBT; please review medication options.")

# --- mid-scenario check: the yellow flag must read CONSIDER right now ---
section("Systematic Caseload Review lifecycle (mid-scenario)")
rows = get("/reports/active-patients", as_of="2026-03-20")
p3_row = next(r for r in rows if r["patient_id"] == p3["patient_id"])
check("flagged patient shows CONSIDER before consultation",
      p3_row["psychiatric_consultation"] == "CONSIDER", str(p3_row["psychiatric_consultation"]))
check("flag is set on the patient record",
      get(f"/patients/{p3['patient_id']}")["needs_psychiatric_review"] is True)

p3_consult = post("/consultations", {
    "patient_id": p3["patient_id"], "provider_id": ramon["provider_id"],
    "consultation_date": "2026-03-24", "recommendations_forwarded": True,
    "notes": "Reviewed in SCR 3/24. Recommend starting sertraline 25 mg and titrating; "
             "re-review in 8 weeks if GAD-7 has not dropped by 5 points.",
})
check("consultation clears the flag",
      get(f"/patients/{p3['patient_id']}")["needs_psychiatric_review"] is False)

visit(p3, e3, "follow_up", "2026-04-21", 30, [("GAD7", 15)], notes="Started sertraline per consult.")
visit(p3, e3, "follow_up", "2026-05-19", 30, [("GAD7", 16)], notes="Still minimal change.")

# P4 David — depression primary; responds and completes in April (achieved_goals).
p4, e4 = intake("PT-1004", "David Kim", "1965-01-25", "2026-02-23", "northside", "depression")
visit(p4, e4, "initial_assessment", "2026-02-24", 45, [("PHQ9", 20)], notes="Intake encounter.")
visit(p4, e4, "follow_up", "2026-03-23", 30, [("PHQ9", 12)], notes="Good engagement.")
visit(p4, e4, "follow_up", "2026-04-20", 30, [("PHQ9", 9)], notes="Response achieved; wrap-up planned.")

# P5 Emma — pediatric anxiety (SCARED): tracked, but unscored thresholds.
p5, e5 = intake("PT-1005", "Emma Tran", "2013-05-20", "2026-03-02", "westend", "anxiety")
visit(p5, e5, "initial_assessment", "2026-03-03", 40, [("SCARED", 42)], notes="Pediatric intake with parent.")
visit(p5, e5, "follow_up", "2026-04-06", 30, [("SCARED", 30)])
visit(p5, e5, "follow_up", "2026-05-04", 30, [("SCARED", 20)])

# P6 Frank — hard to reach; attempts, one visit, removed as not_engaged.
p6, e6 = intake("PT-1006", "Frank Miller", "1972-09-14", "2026-03-09", "westend", "depression")
a1 = visit(p6, e6, "contact_attempt", "2026-03-10", 5)
a2 = visit(p6, e6, "contact_attempt", "2026-03-17", 5)
p6_ia = visit(p6, e6, "initial_assessment", "2026-03-24", 45, [("PHQ9", 22)],
              notes="Finally reached. Severe symptoms; ambivalent about treatment.")
a3 = visit(p6, e6, "contact_attempt", "2026-04-14", 5)
check("attempt numbering: #1, #2, then resets after a real visit",
      (a1["attempt_number"], a2["attempt_number"], a3["attempt_number"]) == (1, 2, 1),
      str((a1["attempt_number"], a2["attempt_number"], a3["attempt_number"])))

# ---------------------------------------------------------------------------
# Removal: close both episodes; patients must stop counting afterward.
# ---------------------------------------------------------------------------
section("Removing patients (episode close -> deactivation cascade)")
patch(f"/episodes/{e4['episode_id']}", {"end_date": "2026-04-30", "end_reason": "achieved_goals"})
patch(f"/patients/{p4['patient_id']}", {"deactivation_date": "2026-04-30"})
patch(f"/episodes/{e6['episode_id']}", {"end_date": "2026-04-28", "end_reason": "not_engaged"})
patch(f"/patients/{p6['patient_id']}", {"deactivation_date": "2026-04-28"})

for pid, label in [(p4["patient_id"], "P4"), (p6["patient_id"], "P6")]:
    statuses = get(f"/episodes/{e4['episode_id'] if label == 'P4' else e6['episode_id']}/status/history")
    check(f"{label} treatment status cascaded to deactivated",
          statuses[-1]["status"] == "deactivated", str(statuses[-1]))

# ---------------------------------------------------------------------------
# 1. Intake round-trip and patient info placement
# ---------------------------------------------------------------------------
section("Patient intake and personal information placement")
p1_back = get(f"/patients/{p1['patient_id']}")
check("demographics round-trip", p1_back["name"] == "Alice Nguyen"
      and p1_back["race_ethnicity"] == ["Asian"]
      and p1_back["program_eligibility"] == {"medicaid_plan": "Standard"}
      and p1_back["consent_date"] == "2026-02-02")

dash1 = get(f"/reports/clinical-dashboard/{p1['patient_id']}")
check("dashboard: demographics", dash1["mrn"] == "PT-1001" and dash1["payer"] == "Medicaid")
check("dashboard: care team shows both current providers",
      sorted(pr["role"] for pr in dash1["current_providers"]) == ["care_manager", "psychiatric_consultant"])
check("dashboard: clinic", [c["clinic_id"] for c in dash1["current_clinics"]] == ["northside"])
check("dashboard: current status RPP", dash1["current_status"] == "relapse_prevention_plan")
check("dashboard: all 5 scores present", len(dash1["symptom_scores"]) == 5)
check("dashboard: medication with catalog name",
      dash1["medications"][0]["medication_name"] == "Sertraline (Zoloft)"
      and dash1["medications"][0]["is_current"] is True)
check("dashboard: profile entries present with dates",
      len(dash1["profile_entries"]) == 2
      and all(e["recorded_date"] == "2026-02-03" for e in dash1["profile_entries"]))
t1 = dash1["measure_trends"]
check("dashboard: one trend graph for single diagnosis",
      len(t1) == 1 and t1[0]["condition"] == "depression" and t1[0]["measure_type"] == "PHQ9")
check("dashboard: trend has full series and outcome flags",
      [p["score_value"] for p in t1[0]["scores"]] == [18, 12, 8, 4, 3]
      and t1[0]["is_response"] is True and t1[0]["is_remission"] is True)

dash2 = get(f"/reports/clinical-dashboard/{p2['patient_id']}")
t2 = dash2["measure_trends"]
check("dashboard: two graphs for two diagnoses, primary first",
      len(t2) == 2 and (t2[0]["condition"], t2[0]["is_primary"]) == ("anxiety", True)
      and (t2[1]["condition"], t2[1]["is_primary"]) == ("depression", False))
check("dashboard: anxiety trend GAD-7 response+remission",
      t2[0]["measure_type"] == "GAD7" and t2[0]["is_response"] is True and t2[0]["is_remission"] is True)
e2_back = get(f"/episodes/{e2['episode_id']}")
check("baseline re-anchored to primary-mapped GAD-7 (PHQ-9 was recorded first)",
      e2_back["baseline_measure_type"] == "GAD7" and e2_back["baseline_score"] == 16,
      str((e2_back["baseline_measure_type"], e2_back["baseline_score"])))

# ---------------------------------------------------------------------------
# 2. Encounter notes and consultation notes: later viewing
# ---------------------------------------------------------------------------
section("Encounter and consultation notes")
p2_contacts = get("/contacts", patient_id=p2["patient_id"])
ia = next(c for c in p2_contacts if c["contact_type"] == "initial_assessment")
check("encounter note persisted and retrievable",
      ia["notes"].startswith("Intake encounter. Panic sx"))
check("every completed P2 contact carries its note",
      all(c["notes"] for c in p2_contacts if c["contact_type"] != "contact_attempt"))

p3_contacts = get("/contacts", patient_id=p3["patient_id"])
flagging = next(c for c in p3_contacts if c["discuss_with_psychiatric_consultant"])
check("notes-for-consultant travels with the flagging contact",
      flagging["notes_for_consultant"].startswith("No improvement after 4 weeks"))

p3_consults = get("/consultations", patient_id=p3["patient_id"])
check("consultation note persisted and retrievable",
      len(p3_consults) == 1 and p3_consults[0]["notes"].startswith("Reviewed in SCR 3/24")
      and p3_consults[0]["recommendations_forwarded"] is True)

p1_contacts = get("/contacts", patient_id=p1["patient_id"])
rpp = next(c for c in p1_contacts if c["contact_type"] == "relapse_prevention_plan")
check("RPP plan content persists over HTTP",
      rpp["other_treatments"].startswith("Weekly counseling")
      and "Sleeping past noon" in rpp["personal_warning_signs"]
      and "hiking group" in rpp["stress_reduction_plan"]
      and rpp["additional_comments"].startswith("Copy of plan")
      and rpp["medications_confirmation"] == "confirmed_with_patient")

bad_rpp_fields = client.post("/contacts", headers=H, json={
    "patient_id": p1["patient_id"], "episode_id": e1["episode_id"],
    "contact_type": "follow_up", "contact_date": "2026-06-20",
    "personal_warning_signs": "should be rejected on a follow-up",
})
check("RPP plan fields rejected on a non-RPP contact (422)",
      bad_rpp_fields.status_code == 422, str(bad_rpp_fields.status_code))

contact_scores = get(f"/contacts/{p6_ia['contact_id']}/scores")
check("scores retrievable per contact", len(contact_scores) == 1
      and contact_scores[0]["score_value"] == 22)

# ---------------------------------------------------------------------------
# 3. Active Patients report (caseload list)
# ---------------------------------------------------------------------------
section("Active Patients report")
rows = get("/reports/active-patients", as_of="2026-07-31")
by_id = {r["patient_id"]: r for r in rows}
check("removed patients absent; 4 active rows",
      len(rows) == 4 and p4["patient_id"] not in by_id and p6["patient_id"] not in by_id,
      str(sorted(by_id)))
r1 = by_id[p1["patient_id"]]
check("P1 row: status/scores/sessions/dates",
      r1["status"] == "relapse_prevention_plan" and (r1["phq9_first"], r1["phq9_last"]) == (18, 3)
      and r1["session_count"] == 5 and r1["initial_assessment_date"] == "2026-02-03"
      and r1["relapse_prevention_plan_date"] == "2026-06-02"
      and r1["weeks_since_initial_assessment"] == 25)
check("P1 psychotropic column true (catalog med)", r1["psychotropic_medications"] is True)
check("P2 psychotropic column false (free-text med only)",
      by_id[p2["patient_id"]]["psychotropic_medications"] is False)
check("P3 consultation column shows the review date",
      by_id[p3["patient_id"]]["psychiatric_consultation"] == "2026-03-24")
check("P5 age computed from DOB", by_id[p5["patient_id"]]["age"] == 13,
      str(by_id[p5["patient_id"]]["age"]))
clinic_rows = get("/reports/active-patients", clinic_id="westend", as_of="2026-07-31")
check("clinic filter works", sorted(r["patient_id"] for r in clinic_rows)
      == sorted([p3["patient_id"], p5["patient_id"]]))

# ---------------------------------------------------------------------------
# 4. Caseload Statistics: condition-split population metrics
# ---------------------------------------------------------------------------
section("Caseload Statistics (per provider, condition-split)")
stats = get("/reports/caseload-statistics", group_by="provider", as_of="2026-07-31")
dana_row = next(r for r in stats if r["group_key"] == str(dana["provider_id"]))
check("caseload size counts only active patients", dana_row["caseload_size"] == 4)
check("avg visits per patient", dana_row["avg_visits_per_patient"] == 4.0,
      str(dana_row["avg_visits_per_patient"]))
check("avg session duration excludes attempts", dana_row["avg_session_duration_minutes"] == 33.4,
      str(dana_row["avg_session_duration_minutes"]))
check("scale completion 100%", dana_row["pct_contacts_with_completed_scale"] == 100.0)
check("depression bucket: P1 only — 1/1 response, 1/1 remission",
      (dana_row["depression_response_count"], dana_row["depression_response_denominator"]) == (1, 1)
      and (dana_row["depression_remission_count"], dana_row["depression_remission_denominator"]) == (1, 1))
check("anxiety bucket: P2+P3 — response 1/2, remission 1/2 (P2's PHQ-9 did NOT leak into depression)",
      (dana_row["anxiety_response_count"], dana_row["anxiety_response_denominator"]) == (1, 2)
      and (dana_row["anxiety_remission_count"], dana_row["anxiety_remission_denominator"]) == (1, 2))
check("pediatric SCARED patient excluded from adult rates (denominators say so)",
      dana_row["anxiety_response_denominator"] == 2)
check("avg first/last scores per measure",
      # PHQ-9 firsts: Alice 18, Ben 15 -> 16.5. Lasts: 3, 6 -> 4.5.
      # GAD-7 firsts: Ben 16, Carla 17 -> 16.5. Lasts: 4, 16 -> 10.0.
      (dana_row["avg_phq9_first"], dana_row["avg_phq9_last"]) == (16.5, 4.5)
      and (dana_row["avg_gad7_first"], dana_row["avg_gad7_last"]) == (16.5, 10.0)
      and dana_row["avg_pcl5_first"] is None,
      str((dana_row["avg_phq9_first"], dana_row["avg_phq9_last"],
           dana_row["avg_gad7_first"], dana_row["avg_gad7_last"])))
check("combined response/remission pools depression + anxiety (disjoint buckets)",
      (dana_row["combined_response_count"], dana_row["combined_response_denominator"]) == (2, 3)
      and (dana_row["combined_remission_count"], dana_row["combined_remission_denominator"]) == (2, 3),
      str((dana_row["combined_response_count"], dana_row["combined_response_denominator"],
           dana_row["combined_remission_count"], dana_row["combined_remission_denominator"])))
check("CTMS aggregate columns", dana_row["patients_with_contact_count"] == 4
      and dana_row["rpp_count"] == 1 and dana_row["flagged_count"] == 0
      and dana_row["with_consultation_count"] == 1,
      str((dana_row["patients_with_contact_count"], dana_row["rpp_count"],
           dana_row["flagged_count"], dana_row["with_consultation_count"])))
check("not improving without recent consultation flags P3 only",
      dana_row["not_improving_without_consultation_count"] == 1,
      str(dana_row["not_improving_without_consultation_count"]))

clinic_stats = get("/reports/caseload-statistics", group_by="clinic", as_of="2026-07-31")
by_clinic = {r["group_key"]: r for r in clinic_stats}
check("clinic rollup: northside=2 (P4 removed), westend=2 (P6 removed)",
      by_clinic["northside"]["caseload_size"] == 2 and by_clinic["westend"]["caseload_size"] == 2,
      str({k: v["caseload_size"] for k, v in by_clinic.items()}))

# ---------------------------------------------------------------------------
# 5. Quality Metrics: month-by-month, removal semantics
# ---------------------------------------------------------------------------
section("CoCM Quality Metrics (monthly, calendar-month caseload)")
months = {(m["year"], m["month"]): m for m in get("/reports/quality-metrics", as_of="2026-07-31")}
check("twelve rows ending July 2026", len(months) == 12 and (2026, 7) in months and (2025, 8) in months)

feb, mar, apr = months[(2026, 2)], months[(2026, 3)], months[(2026, 4)]
may, jun, jul = months[(2026, 5)], months[(2026, 6)], months[(2026, 7)]

check("Feb caseload=4 (P1-P4 enrolled)", feb["caseload_size"] == 4, str(feb["caseload_size"]))
check("Mar caseload=6 (all enrolled)", mar["caseload_size"] == 6, str(mar["caseload_size"]))
check("Apr caseload=6 (removals happen at month end)", apr["caseload_size"] == 6)
check("May caseload=4 — REMOVED PATIENTS NO LONGER COUNT", may["caseload_size"] == 4,
      str(may["caseload_size"]))
check("Jun/Jul caseload stays 4", jun["caseload_size"] == 4 and jul["caseload_size"] == 4)

check("Feb engagement 4/4", (feb["engagement_count"], feb["engagement_denominator"]) == (4, 4))
check("Apr engagement 5/6 (P6 attempt-only month doesn't count as engagement)",
      (apr["engagement_count"], apr["engagement_denominator"]) == (5, 6)
      and apr["engagement_percentage"] == 83.3)
check("May engagement 4/4 (removed patients out of the denominator)",
      (may["engagement_count"], may["engagement_denominator"]) == (4, 4))
check("Jun engagement 1/4 (only P1's RPP visit)", (jun["engagement_count"], jun["engagement_denominator"]) == (1, 4))
check("Jul engagement 0/4", (jul["engagement_count"], jul["engagement_denominator"]) == (0, 4))

check("Apr depression response 2/2 (P1 and P4; P6 has no follow-up score)",
      (apr["depression_response_count"], apr["depression_response_denominator"]) == (2, 2))
check("May depression response 1/1 (P4 removed — dropped from the rate, not counted as failure)",
      (may["depression_response_count"], may["depression_response_denominator"]) == (1, 1))
check("Apr anxiety improvement 1/2 (P2 yes, P3 no)",
      (apr["anxiety_improvement_count"], apr["anxiety_improvement_denominator"]) == (1, 2))
check("Apr pediatric anxiety 0/1 (SCARED tracked but unscored — conservative default)",
      (apr["pediatric_anxiety_improvement_count"], apr["pediatric_anxiety_improvement_denominator"]) == (0, 1))
check("Mar psychiatric case review 1/6 (P3's consultation)",
      (mar["psychiatric_case_review_count"], mar["psychiatric_case_review_denominator"]) == (1, 6))
check("caseload reach stays null (no eligible-population denominator exists)",
      all(m["caseload_reach"] is None for m in months.values()))

# ---------------------------------------------------------------------------
# 6. Completed Episode Statistics
# ---------------------------------------------------------------------------
section("Completed Episode Statistics (2026)")
ces = get("/reports/completed-episode-statistics", year=2026)
check("two completed episodes", ces["total_completed_episodes"] == 2)
check("deactivation reasons: achieved_goals=1, not_engaged=1, none unrecorded",
      ces["deactivation_reason_counts"]["achieved_goals"] == 1
      and ces["deactivation_reason_counts"]["not_engaged"] == 1
      and ces["deactivation_reason_counts"]["not_recorded"] == 0)
check("avg weeks in treatment 8.3", ces["avg_weeks_in_treatment"] == 8.3,
      str(ces["avg_weeks_in_treatment"]))
check("avg contacts 2.0 (attempts excluded)", ces["avg_contacts_per_episode"] == 2.0)
check("depression outcome 1/1 (P4 responded; P6 single score excluded from denominator)",
      (ces["depression_response_count"], ces["depression_response_denominator"]) == (1, 1))

# ---------------------------------------------------------------------------
# 7. Reminders and referral follow-up
# ---------------------------------------------------------------------------
section("Reminders")
pending = get("/reminders")
pending_by_patient = {}
for r in pending:
    pending_by_patient.setdefault(r["patient_id"], []).append(r)
check("removed patients have no pending reminders",
      p4["patient_id"] not in pending_by_patient and p6["patient_id"] not in pending_by_patient)
p2_reminders = pending_by_patient.get(p2["patient_id"], [])
referral_rem = [r for r in p2_reminders if r["reminder_type"] == "referral_followup"]
check("referral created its 4-week follow-up reminder (due 4/6)",
      len(referral_rem) == 1 and referral_rem[0]["due_date"] == "2026-04-06"
      and referral_rem[0]["referral_id"] is not None)
p1_appt = [r for r in pending_by_patient.get(p1["patient_id"], [])
           if r["reminder_type"] == "appointment"]
check("P1 appointment reminder follows RPP cadence (6/2 + 28 days)",
      len(p1_appt) == 1 and p1_appt[0]["due_date"] == "2026-06-30",
      str([r["due_date"] for r in p1_appt]))

# ---------------------------------------------------------------------------
# 8. Monthly Time Tracker: removed patients keep their billed minutes
# ---------------------------------------------------------------------------
section("Monthly Time Tracker")
tt = {row["patient_id"]: row for row in get("/reports/time-tracker", as_of="2026-07-31")}
check("all six patients appear (removal doesn't erase billed minutes)",
      all(p["patient_id"] in tt for p in [p1, p2, p3, p4, p5, p6]))
check("P4 total minutes 105 across Feb-Apr", tt[p4["patient_id"]]["total_minutes"] == 105)
p6_minutes = {(m["year"], m["month"]): m["minutes"] for m in tt[p6["patient_id"]]["months"]}
check("P6 total 45 — contact attempts' minutes excluded",
      tt[p6["patient_id"]]["total_minutes"] == 45 and p6_minutes[(2026, 4)] == 0,
      str(tt[p6["patient_id"]]["total_minutes"]))
check("P1 total minutes 160", tt[p1["patient_id"]]["total_minutes"] == 160)

# ---------------------------------------------------------------------------
# 9. DRR (HEDIS window sanity)
# ---------------------------------------------------------------------------
section("DRR report (4-8 month follow-up window)")
# Every PHQ-9-baseline episode here has a 2026 baseline, so with as_of in
# August none of their 4-8 month windows have closed yet: the cohort is
# empty because those outcomes are genuinely still unknown, NOT failures.
drr_early = get("/reports/drr", year=2026, as_of="2026-08-07")
check("windows still open -> episodes excluded rather than counted as failures",
      drr_early == [], str(drr_early))

# By November, P1 (baseline 2/3, window 6/3-10/3) and P4 (baseline 2/24,
# window 6/24-10/24) have closed windows and enter the cohort; P6 (baseline
# 3/24, window 7/24-11/24) has not, and P2's baseline is GAD-7 so it's not
# an index episode at all.
drr = get("/reports/drr", year=2026, as_of="2026-11-01")
total_index = sum(r["index_episode_count"] for r in drr)
check("2 index episodes once their windows close (P6 still open, P2 is GAD-7-baseline)",
      total_index == 2, str(drr))
northside = next((r for r in drr if r["clinic_id"] == "northside"), None)
check("both group under northside with 0 follow-ups "
      "(P1's last PHQ-9 6/2 misses its 6/3 window start by a day; P4's ends 4/20)",
      northside is not None and northside["index_episode_count"] == 2
      and northside["follow_up_phq9_count"] == 0, str(northside))

# ---------------------------------------------------------------------------
# 10. Frontend write-path contract (Phase 12)
# ---------------------------------------------------------------------------
# Replays the EXACT payload shapes the contact form and consultation note
# send, including the shapes only the UI can produce: nulls where a "—"
# dropdown was left alone, a directly-typed total alongside a matrix total,
# every location value, the RPP plan block, and each rejection the form
# relies on the server to enforce. A frontend field silently dropped at the
# route layer is a real bug this codebase has already shipped once (see
# Contact.notes in CLAUDE.md's Build Status), so these assert round-trips,
# not just status codes.
section("Frontend write-path contract (contact + consultation forms)")

AUG = "2026-08"
p7, e7 = intake("PT-1007", "Grace Liu", "1990-02-14", f"{AUG}-03", "northside", "depression")


def form_contact(**overrides):
    """A payload shaped exactly as RecordContact.tsx builds it."""
    body = {
        "patient_id": p7["patient_id"],
        "episode_id": e7["episode_id"],
        "provider_id": dana["provider_id"],
        "contact_type": "follow_up",
        "contact_date": f"{AUG}-05",
        "location": None,
        "duration_minutes": None,
        "discuss_with_psychiatric_consultant": False,
        "notes_for_consultant": None,
        "notes": None,
        "scores": [],
    }
    body.update(overrides)
    return body


def raw_post(path, body):
    return client.post(path, json=body, headers=H)


# --- every dropdown left at "—" sends explicit nulls -------------------------
minimal = post("/contacts", form_contact(contact_date=f"{AUG}-04"))
check("all-null optional fields accepted (every dropdown left at '—')",
      minimal["location"] is None and minimal["duration_minutes"] is None
      and minimal["notes"] is None and minimal["notes_for_consultant"] is None)

# --- initial assessment: matrix total + full session footer ------------------
ia = post("/contacts", form_contact(
    contact_type="initial_assessment", contact_date=f"{AUG}-05",
    location="in_clinic", duration_minutes=45,
    notes="Intake. Depressed mood 6 weeks; started behavioral activation.",
    scores=[{"measure_type": "PHQ9", "score_value": 20}],
))
check("initial assessment round-trips every session-footer field",
      ia["location"] == "in_clinic" and ia["duration_minutes"] == 45
      and ia["notes"].startswith("Intake.") and ia["provider_id"] == dana["provider_id"])

# --- follow-up: matrix score + directly-typed total, and the consultant flag -
fu = post("/contacts", form_contact(
    contact_date=f"{AUG}-06", location="phone", duration_minutes=30,
    discuss_with_psychiatric_consultant=True,
    notes_for_consultant="PHQ-9 still 14 after 4 weeks; consider medication.",
    notes="Follow-up by phone.",
    scores=[{"measure_type": "PHQ9", "score_value": 14},
            {"measure_type": "GAD7", "score_value": 7}],
))
fu_scores = get(f"/contacts/{fu['contact_id']}/scores")
check("two scales on one contact both persist (matrix + typed total)",
      sorted((s["measure_type"], s["score_value"]) for s in fu_scores)
      == [("GAD7", 7), ("PHQ9", 14)], str(fu_scores))
check("discuss-with-consultant checkbox lights the yellow flag",
      get(f"/patients/{p7['patient_id']}")["needs_psychiatric_review"] is True)

rows = get("/reports/active-patients")
g_row = next(r for r in rows if r["patient_id"] == p7["patient_id"])
check("flagged patient reads CONSIDER on the caseload",
      g_row["psychiatric_consultation"] == "CONSIDER")
check("caseload score indicators are fresh (no staleness asterisk on today's scores)",
      g_row["phq9_stale"] is False and g_row["phq9_single_score"] is False
      # Baseline 20 -> last 14 is a 30% improvement and still >= 10, so the
      # confirmed CTMS rule paints this red.
      and g_row["phq9_last_color"] == "red",
      str((g_row["phq9_stale"], g_row["phq9_single_score"], g_row["phq9_last_color"])))

# --- consultation note: clears the flag, and its minutes are billable --------
consult = post("/consultations", {
    "patient_id": p7["patient_id"], "provider_id": ramon["provider_id"],
    "consultation_date": f"{AUG}-07", "duration_minutes": 20,
    "recommendations_forwarded": True, "flagged_for_next_review": False,
    "flag_reason": None,
    "notes": "Reviewed 8/7. Start sertraline 50mg; re-check PHQ-9 in 4 weeks.",
})
check("consultation note round-trips minutes and findings",
      consult["duration_minutes"] == 20 and consult["notes"].startswith("Reviewed 8/7"))
check("recording the consultation clears the yellow flag",
      get(f"/patients/{p7['patient_id']}")["needs_psychiatric_review"] is False)

# --- care team collaboration: billable, but not an encounter -----------------
collab = post("/contacts", form_contact(
    contact_type="care_team_collaboration", contact_date=f"{AUG}-10",
    duration_minutes=15, notes="Coordinated with PCP on medication start.",
))
check("care team collaboration accepted with minutes and a note",
      collab["duration_minutes"] == 15)

# --- contact attempts: the collaboration must not reset the counter ----------
att1 = post("/contacts", form_contact(contact_type="contact_attempt", contact_date=f"{AUG}-11"))
att2 = post("/contacts", form_contact(contact_type="contact_attempt", contact_date=f"{AUG}-12"))
check("attempt numbering survives an interleaved collaboration",
      (att1["attempt_number"], att2["attempt_number"]) == (1, 2),
      str((att1["attempt_number"], att2["attempt_number"])))

# --- Minutes This Month vs Monthly Time Tracker must agree -------------------
# The form lets a user put minutes on an attempt, which is what makes this
# worth asserting: both surfaces answer "minutes of service this month" and
# must exclude the same contact types (attempts out, collaboration in, plus
# psychiatric consultations).
post("/contacts", form_contact(contact_type="contact_attempt",
                               contact_date=f"{AUG}-12", duration_minutes=5))
expected_minutes = 45 + 30 + 15 + 20  # IA + FU + collab + consultation; attempts excluded
rows = get("/reports/active-patients")
g_row = next(r for r in rows if r["patient_id"] == p7["patient_id"])
tracker = {r["patient_id"]: r for r in get("/reports/time-tracker")}
g_tracker = tracker[p7["patient_id"]]
aug_minutes = next(m["minutes"] for m in g_tracker["months"] if (m["year"], m["month"]) == (2026, 8))
check("Minutes This Month excludes contact-attempt minutes",
      g_row["minutes_this_month"] == expected_minutes,
      f'got {g_row["minutes_this_month"]}, expected {expected_minutes}')
check("Minutes This Month agrees with the Monthly Time Tracker",
      g_row["minutes_this_month"] == aug_minutes,
      f'caseload {g_row["minutes_this_month"]} vs tracker {aug_minutes}')

# --- session count counts encounters only -----------------------------------
check("# Sessions counts encounters only (collaboration and attempts excluded)",
      g_row["session_count"] == 3,  # the all-null follow-up, the IA, and the scored follow-up
      str(g_row["session_count"]))

# --- RPP: the full plan block, and the status cascade ------------------------
rpp = post("/contacts", form_contact(
    contact_type="relapse_prevention_plan", contact_date=f"{AUG}-12",
    location="virtual", duration_minutes=25,
    notes="RPP completed with patient.",
    other_treatments="Group CBT on Tuesdays",
    personal_warning_signs="Withdrawing from friends; skipping meals",
    stress_reduction_plan="Morning walk; weekly call with sister",
    additional_comments="Plan emailed to PCP.",
    medications_confirmation="deferred",
    scores=[{"measure_type": "PHQ9", "score_value": 4}],
))
check("RPP plan block round-trips all five fields",
      rpp["other_treatments"] == "Group CBT on Tuesdays"
      and rpp["personal_warning_signs"].startswith("Withdrawing")
      and rpp["stress_reduction_plan"].startswith("Morning walk")
      and rpp["additional_comments"] == "Plan emailed to PCP."
      and rpp["medications_confirmation"] == "deferred")
check("RPP contact cascades treatment status to relapse_prevention_plan",
      get(f"/episodes/{e7['episode_id']}/status/history")[-1]["status"]
      == "relapse_prevention_plan")

# --- every confirmed location value round-trips ------------------------------
locations = set()
for i, loc in enumerate(("phone", "in_clinic", "virtual")):
    created = post("/contacts", form_contact(contact_date=f"{AUG}-1{3 + i}", location=loc))
    locations.add(created["location"])
check("all three confirmed locations round-trip", locations == {"phone", "in_clinic", "virtual"},
      str(sorted(locations)))

# --- rejections the form depends on the server to enforce -------------------
bad_rpp = raw_post("/contacts", form_contact(personal_warning_signs="not on a follow-up"))
check("RPP plan fields rejected on a follow-up (422)", bad_rpp.status_code == 422,
      str(bad_rpp.status_code))

bad_attempt = raw_post("/contacts", form_contact(
    contact_type="contact_attempt",
    scores=[{"measure_type": "PHQ9", "score_value": 10}]))
check("scores rejected on a contact attempt (422)", bad_attempt.status_code == 422,
      str(bad_attempt.status_code))

bad_collab = raw_post("/contacts", form_contact(
    contact_type="care_team_collaboration",
    scores=[{"measure_type": "PHQ9", "score_value": 10}]))
check("scores rejected on care team collaboration (422)", bad_collab.status_code == 422,
      str(bad_collab.status_code))

bad_episode = raw_post("/contacts", form_contact(
    episode_id=None, scores=[{"measure_type": "PHQ9", "score_value": 10}]))
check("scores without an episode rejected (422)", bad_episode.status_code == 422,
      str(bad_episode.status_code))

bad_location = raw_post("/contacts", form_contact(location="in_person"))
check("retired location value rejected (422)", bad_location.status_code == 422,
      str(bad_location.status_code))

bad_measure = raw_post("/contacts", form_contact(
    scores=[{"measure_type": "AUDITC", "score_value": 4}]))
check("unknown measure type rejected (422)", bad_measure.status_code == 422,
      str(bad_measure.status_code))

# --- consultation that flags a future review re-sets the flag ---------------
post("/consultations", {
    "patient_id": p7["patient_id"], "provider_id": ramon["provider_id"],
    "consultation_date": f"{AUG}-12", "duration_minutes": 15,
    "recommendations_forwarded": False, "flagged_for_next_review": True,
    "flag_reason": "Confirm sertraline tolerance",
    "notes": "Re-review after 4 weeks on sertraline.",
})
check("a consultation flagging a future review leaves the flag SET",
      get(f"/patients/{p7['patient_id']}")["needs_psychiatric_review"] is True)

# --- the dashboard the form redirects to reflects everything just written ----
dash = get(f"/reports/clinical-dashboard/{p7['patient_id']}")
check("dashboard shows the depression trend the form's scores built",
      len(dash["measure_trends"]) == 1
      and dash["measure_trends"][0]["measure_type"] == "PHQ9"
      and [p["score_value"] for p in dash["measure_trends"][0]["scores"]] == [20, 14, 4]
      and dash["measure_trends"][0]["is_response"] is True
      and dash["measure_trends"][0]["is_remission"] is True,
      str(dash["measure_trends"]))
check("dashboard consultations carry their notes and minutes",
      len(dash_consults := get("/consultations", patient_id=p7["patient_id"])) == 2
      and all(c["notes"] for c in dash_consults))

# ---------------------------------------------------------------------------
# 11. Report contract + cross-report consistency (Phase 12)
# ---------------------------------------------------------------------------
# The report screens are read-only, so their failure mode isn't a rejected
# write — it's a field that quietly renamed or vanished (the UI renders a
# blank cell and nobody notices) or two reports disagreeing about the same
# underlying number. This section pins both down:
#
#   1. Every key the frontend reads is present, for all five reports.
#   2. Every (count, denominator, percentage) triple is internally
#      consistent — the arithmetic invariant that caught the Caseload
#      Statistics "All groups" 0% bug on the frontend side.
#   3. Numbers that appear in more than one report agree.
#   4. Measures with no confirmed threshold never report a nonzero numerator.
section("Report contract and cross-report consistency")


def missing_keys(payload: dict, required: set) -> list:
    return sorted(required - set(payload))


def check_rate_arithmetic(label: str, payload: dict, fallback_denominator_key: str | None = None):
    """
    For every `<name>_count`, verify `<name>_percentage` really is
    100*count/denominator rounded to one decimal — using `<name>_denominator`
    when present, else the row's own fallback (caseload_size for the
    caseload-column percentages, which share that denominator by
    convention).
    """
    problems = []
    for key, count in payload.items():
        if not key.endswith("_count") or not isinstance(count, int):
            continue
        stem = key[: -len("_count")]
        pct_key = f"{stem}_percentage"
        if pct_key not in payload:
            continue
        denom_key = f"{stem}_denominator"
        if denom_key in payload:
            denominator = payload[denom_key]
        elif fallback_denominator_key:
            denominator = payload[fallback_denominator_key]
        else:
            continue
        expected = round(100 * count / denominator, 1) if denominator else 0.0
        if abs(payload[pct_key] - expected) > 0.05:
            problems.append(f"{pct_key}={payload[pct_key]} expected {expected} ({count}/{denominator})")
    check(f"{label}: every rate's percentage matches its own count/denominator",
          not problems, "; ".join(problems))


# --- Caseload Statistics -----------------------------------------------------
CASELOAD_KEYS = {
    "group_type", "group_key", "group_label", "caseload_size",
    "patients_with_contact_count", "patients_with_contact_percentage",
    "avg_visits_per_patient", "avg_session_duration_minutes",
    "pct_contacts_with_completed_scale",
    "rpp_count", "rpp_percentage", "flagged_count", "flagged_percentage",
    "with_consultation_count", "with_consultation_percentage",
    "not_improving_without_consultation_count", "avg_psychiatric_case_reviews",
    "avg_phq9_first", "avg_phq9_last", "avg_gad7_first", "avg_gad7_last",
    "avg_pcl5_first", "avg_pcl5_last",
    "combined_response_count", "combined_response_denominator", "combined_response_percentage",
    "combined_remission_count", "combined_remission_denominator", "combined_remission_percentage",
    "depression_response_count", "depression_response_denominator", "depression_response_percentage",
    "depression_remission_count", "depression_remission_denominator", "depression_remission_percentage",
    "anxiety_response_count", "anxiety_response_denominator", "anxiety_response_percentage",
    "anxiety_remission_count", "anxiety_remission_denominator", "anxiety_remission_percentage",
}
provider_stats = get("/reports/caseload-statistics", group_by="provider")
check("Caseload Statistics: every field the UI reads is present",
      provider_stats and not missing_keys(provider_stats[0], CASELOAD_KEYS),
      str(missing_keys(provider_stats[0], CASELOAD_KEYS)) if provider_stats else "no rows")
for row in provider_stats:
    check_rate_arithmetic(f"Caseload Statistics [{row['group_label']}]", row,
                          fallback_denominator_key="caseload_size")

check("combined outcome buckets equal depression + anxiety (disjoint by the primary-diagnosis rule)",
      all(r["combined_response_count"] == r["depression_response_count"] + r["anxiety_response_count"]
          and r["combined_response_denominator"]
          == r["depression_response_denominator"] + r["anxiety_response_denominator"]
          for r in provider_stats))

# --- Quality Metrics ---------------------------------------------------------
QM_STEMS = ["engagement", "measures_completion", "depression_response", "anxiety_improvement",
            "ptsd_improvement", "pediatric_anxiety_improvement",
            "pediatric_depression_response", "pediatric_adhd_improvement",
            "psychiatric_case_review"]
QM_KEYS = {"year", "month", "caseload_size", "caseload_reach"} | {
    f"{stem}_{suffix}" for stem in QM_STEMS for suffix in ("count", "denominator", "percentage")
}
quality = get("/reports/quality-metrics")
check("Quality Metrics: every field the UI reads is present",
      not missing_keys(quality[0], QM_KEYS), str(missing_keys(quality[0], QM_KEYS)))
for month in quality:
    check_rate_arithmetic(f"Quality Metrics [{month['year']}-{month['month']:02d}]", month)

check("Caseload Reach is null in every month (no eligible-population denominator exists)",
      all(m["caseload_reach"] is None for m in quality))
check("unconfirmed-threshold measures never report a nonzero numerator",
      all(m[f"{stem}_count"] == 0 for m in quality
          for stem in ("ptsd_improvement", "pediatric_anxiety_improvement",
                       "pediatric_depression_response", "pediatric_adhd_improvement")))
check("no month's engagement or outcome count exceeds its own denominator",
      all(m[f"{stem}_count"] <= m[f"{stem}_denominator"] for m in quality for stem in QM_STEMS))

# --- Completed Episode Statistics -------------------------------------------
CES_KEYS = {"year", "total_completed_episodes", "avg_weeks_in_treatment",
            "avg_contacts_per_episode", "relapse_prevention_plan_count",
            "deactivation_reason_counts",
            "depression_response_count", "depression_response_denominator",
            "anxiety_improvement_count", "anxiety_improvement_denominator",
            "ptsd_improvement_count", "ptsd_improvement_denominator"}
ces = get("/reports/completed-episode-statistics", year=2026)
check("Completed Episode Statistics: every field the UI reads is present",
      not missing_keys(ces, CES_KEYS), str(missing_keys(ces, CES_KEYS)))
check("deactivation reasons sum to the completed-episode total (incl. the not_recorded bucket)",
      sum(ces["deactivation_reason_counts"].values()) == ces["total_completed_episodes"],
      f'{sum(ces["deactivation_reason_counts"].values())} vs {ces["total_completed_episodes"]}')
check("a not_recorded bucket exists so silently-closed episodes stay visible",
      "not_recorded" in ces["deactivation_reason_counts"])
check("PTSD improvement stays 0 (PCL-5 threshold unconfirmed)", ces["ptsd_improvement_count"] == 0)

# --- DRR ---------------------------------------------------------------------
DRR_KEYS = {"clinic_id", "index_episode_count",
            "follow_up_phq9_count", "follow_up_phq9_percentage",
            "depression_remission_count", "depression_remission_percentage",
            "depression_response_count", "depression_response_percentage"}
drr_closed = get("/reports/drr", year=2026, as_of="2026-11-01")
check("DRR: every field the UI reads is present",
      drr_closed and not missing_keys(drr_closed[0], DRR_KEYS),
      str(missing_keys(drr_closed[0], DRR_KEYS)) if drr_closed else "no rows")
check("DRR's three rates all use index_episode_count as their denominator",
      all(abs(r["follow_up_phq9_percentage"]
              - (round(100 * r["follow_up_phq9_count"] / r["index_episode_count"], 1)
                 if r["index_episode_count"] else 0)) < 0.05
          for r in drr_closed))
check("no DRR numerator exceeds the eligible cohort",
      all(r["follow_up_phq9_count"] <= r["index_episode_count"]
          and r["depression_remission_count"] <= r["index_episode_count"]
          and r["depression_response_count"] <= r["index_episode_count"]
          for r in drr_closed))
check("DRR remission and response never exceed follow-up completion "
      "(an outcome requires a follow-up score)",
      all(r["depression_remission_count"] <= r["follow_up_phq9_count"]
          and r["depression_response_count"] <= r["follow_up_phq9_count"]
          for r in drr_closed))

# --- Monthly Time Tracker ----------------------------------------------------
tracker_rows = get("/reports/time-tracker")
check("Time Tracker: every field the UI reads is present",
      tracker_rows and not missing_keys(tracker_rows[0], {"patient_id", "mrn", "name", "months", "total_minutes"})
      and not missing_keys(tracker_rows[0]["months"][0], {"year", "month", "minutes"}))
check("Time Tracker spans 13 months (current plus trailing 12)",
      all(len(r["months"]) == 13 for r in tracker_rows),
      str({len(r["months"]) for r in tracker_rows}))
check("each Time Tracker row's total equals the sum of its months",
      all(r["total_minutes"] == sum(m["minutes"] for m in r["months"]) for r in tracker_rows))
check("Time Tracker months run oldest-first",
      all([(m["year"], m["month"]) for m in r["months"]]
          == sorted((m["year"], m["month"]) for m in r["months"]) for r in tracker_rows))

# --- Cross-report consistency ------------------------------------------------
# The invariant that caught a real bug once already: two surfaces answering
# the same question must agree, patient by patient.
active_rows = get("/reports/active-patients")
tracker_by_patient = {r["patient_id"]: r for r in tracker_rows}
current_month = (2026, 8)
mismatches = []
for row in active_rows:
    tracker_row = tracker_by_patient.get(row["patient_id"])
    tracked = (
        next((m["minutes"] for m in tracker_row["months"]
              if (m["year"], m["month"]) == current_month), 0)
        if tracker_row else 0
    )
    if row["minutes_this_month"] != tracked:
        mismatches.append(f'{row["name"]}: caseload {row["minutes_this_month"]} vs tracker {tracked}')
check("Minutes This Month agrees with the Time Tracker for EVERY active patient",
      not mismatches, "; ".join(mismatches))

qm_current = next(m for m in quality if (m["year"], m["month"]) == current_month)
check("Quality Metrics' current-month caseload is at least the Active Patients count "
      "(it also counts episodes closed mid-month)",
      qm_current["caseload_size"] >= len(active_rows),
      f'{qm_current["caseload_size"]} vs {len(active_rows)}')

clinic_stats = get("/reports/caseload-statistics", group_by="clinic")
flagged_on_caseload = sum(1 for r in active_rows if r["needs_psychiatric_review"])
flagged_in_stats = sum(r["flagged_count"] for r in clinic_stats)
check("flagged-patient counts agree between Active Patients and Caseload Statistics",
      flagged_in_stats == flagged_on_caseload,
      f"stats {flagged_in_stats} vs caseload {flagged_on_caseload}")

rpp_on_caseload = sum(1 for r in active_rows if r["status"] == "relapse_prevention_plan")
rpp_in_stats = sum(r["rpp_count"] for r in clinic_stats)
check("relapse-prevention counts agree between Active Patients and Caseload Statistics",
      rpp_in_stats == rpp_on_caseload, f"stats {rpp_in_stats} vs caseload {rpp_on_caseload}")

# ---------------------------------------------------------------------------
# 12. Audit trail (Phase 13)
# ---------------------------------------------------------------------------
# CLAUDE.md's PHI rule requires an audit entry for every write to patient
# status, a flag, or a score, recording who / what / when. Everything above
# in this script went through the real HTTP API as an authenticated
# provider, so the audit log should now be able to reconstruct that history
# — and every entry should name an actor, because every write came from a
# route. An anonymous entry here means a route lost the caller's identity.
section("Audit trail")

audit_all = get("/audit-log", limit=1000)
check("audit entries were written for the whole scenario", len(audit_all) > 40,
      f"only {len(audit_all)} entries")

anonymous = [e for e in audit_all if e["actor_provider_id"] is None]
check("every audit entry from an HTTP write names its actor",
      not anonymous,
      f"{len(anonymous)} anonymous: {sorted({(e['action'], e['field']) for e in anonymous})}")

check("entries carry a timestamp and an action",
      all(e["occurred_at"] and e["action"] for e in audit_all))

check("audit-log listing is newest-first",
      [e["audit_log_id"] for e in audit_all]
      == sorted((e["audit_log_id"] for e in audit_all), reverse=True))

# --- the three writes the rule names, for one patient -----------------------
p1_audit = get("/audit-log", patient_id=p1["patient_id"], limit=500)
p1_actions = [e["action"] for e in p1_audit]
check("Alice's trail covers scores, status changes and the episode opening",
      "score_recorded" in p1_actions and "status_changed" in p1_actions
      and "episode_opened" in p1_actions,
      str(sorted(set(p1_actions))))
check("every score Alice had recorded appears in her trail",
      sum(1 for a in p1_actions if a == "score_recorded") == 5,
      str(sum(1 for a in p1_actions if a == "score_recorded")))

rpp_status = [
    e for e in p1_audit
    if e["action"] == "status_changed" and e["new_value"] == "relapse_prevention_plan"
]
check("the RPP status cascade is audited and says what caused it",
      len(rpp_status) == 1 and "relapse prevention plan contact" in (rpp_status[0]["context"] or ""),
      str(rpp_status))

# --- a patient's trail is scoped to that patient ----------------------------
check("a patient's trail contains only their own entries",
      all(e["patient_id"] == p1["patient_id"] for e in p1_audit))

# --- the flag lifecycle is attributable both directions ---------------------
p3_audit = get("/audit-log", patient_id=p3["patient_id"], limit=500)
flag_events = [e for e in p3_audit if e["field"] == "needs_psychiatric_review"]
check("Carla's yellow flag reads flag_set then flag_cleared (newest first, so reversed)",
      [e["action"] for e in flag_events] == ["flag_cleared", "flag_set"],
      str([(e["action"], e["old_value"], e["new_value"]) for e in flag_events]))
check("flag entries record the before and after value",
      all(e["old_value"] in ("true", "false") and e["new_value"] in ("true", "false")
          for e in flag_events))

# --- deactivation is attributable ------------------------------------------
p4_audit = get("/audit-log", patient_id=p4["patient_id"], limit=500)
p4_actions = {e["action"] for e in p4_audit}
check("closing David's episode is audited, with the deactivated status cascade",
      "episode_closed" in p4_actions and any(
          e["action"] == "status_changed" and e["new_value"] == "deactivated" for e in p4_audit
      ), str(sorted(p4_actions)))
check("the patient-level deactivation date is audited too",
      "patient_deactivated" in p4_actions, str(sorted(p4_actions)))

# --- the log is append-only over HTTP --------------------------------------
for method, path in (("POST", "/audit-log"), ("PATCH", "/audit-log/1"), ("DELETE", "/audit-log/1")):
    response = client.request(method, path, headers=H, json={} if method != "DELETE" else None)
    check(f"{method} {path} is not a route (audit log is append-only)",
          response.status_code in (404, 405), str(response.status_code))

# ---------------------------------------------------------------------------
print(f"\n{'=' * 50}\nPRESSURE TEST: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
