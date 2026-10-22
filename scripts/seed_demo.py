"""
Demo seed — a realistic CoCM program, dated relative to today.

Distinct from scripts/pressure_test.py, and deliberately so: the pressure
test asserts exact numbers against hardcoded 2026 dates, and those fixed
expectations are what make it catch regressions. This script asserts
nothing. It just produces data that looks like a program running right now,
so every screen demos honestly:

  - Active patients' most recent scores are within 30 days, so the caseload
    list isn't a wall of staleness asterisks.
  - Reminders land in a realistic mix: a few coming due, a couple overdue.
  - History reaches ~18 months back, so CoCM Quality Metrics has activity
    in every one of its twelve months instead of mostly blanks.
  - Some episodes have PHQ-9 baselines in the PREVIOUS calendar year, which
    is the only way the DRR report can show anything: its 4-8 month window
    must have fully closed, so a baseline set this year can't qualify until
    at least September. Run DRR for last year to see real numbers.
  - Patients sit at every stage: brand-new intake, mid-treatment improving,
    not improving and flagged for review, relapse prevention, hard to
    reach, and completed.

Run against a DEDICATED demo database (the script refuses otherwise):

    createdb cocm_registry_demo
    DATABASE_URL=...cocm_registry_demo alembic upgrade head
    DATABASE_URL=...cocm_registry_demo PYTHONPATH=. python3 scripts/seed_demo.py

Sign in afterwards as any care manager listed at the end, or as the
supervisor account it prints.
"""

import calendar
import os
import sys
from datetime import date, timedelta

if "demo" not in os.environ.get("DATABASE_URL", ""):
    sys.exit("Refusing to run: point DATABASE_URL at a dedicated *demo* database first.")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import ProviderRole  # noqa: E402
from app.models.provider import Provider  # noqa: E402
from app.repositories.provider import ProviderRepository  # noqa: E402

client = TestClient(app)
TODAY = date.today()

SUPERVISOR_EMAIL = "demo@neuroflow.com"
SUPERVISOR_PASSWORD = "demo-password"


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


def months_ago(n: int, day: int | None = None) -> str:
    """The same day-of-month n months back, clamped to that month's length."""
    total = TODAY.month - 1 - n
    year = TODAY.year + total // 12
    month = total % 12 + 1
    target_day = day or TODAY.day
    return date(year, month, min(target_day, calendar.monthrange(year, month)[1])).isoformat()


def _bootstrap_and_login() -> dict:
    db = SessionLocal()
    try:
        repo = ProviderRepository(db)
        if repo.get_by_email(SUPERVISOR_EMAIL) is None:
            repo.create(
                Provider(
                    name="Demo Supervisor",
                    role=ProviderRole.CLINIC_SUPERVISOR,
                    email=SUPERVISOR_EMAIL,
                    hashed_password=hash_password(SUPERVISOR_PASSWORD),
                )
            )
    finally:
        db.close()
    login = client.post(
        "/auth/login", json={"email": SUPERVISOR_EMAIL, "password": SUPERVISOR_PASSWORD}
    )
    login.raise_for_status()
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


H = _bootstrap_and_login()


def post(path, body):
    response = client.post(path, json=body, headers=H)
    if response.status_code not in (200, 201):
        raise SystemExit(f"POST {path} -> {response.status_code}: {response.text}")
    return response.json()


def patch(path, body):
    response = client.patch(path, json=body, headers=H)
    if response.status_code != 200:
        raise SystemExit(f"PATCH {path} -> {response.status_code}: {response.text}")
    return response.json()


# ---------------------------------------------------------------------------
# Care team
# ---------------------------------------------------------------------------
priya = post("/providers", {
    "name": "Priya Nandakumar", "role": "care_manager",
    "email": "priya@neuroflow.com", "password": "demo-password",
    "phone": "206-555-0142",
})
dana = post("/providers", {
    "name": "Dana Whitfield", "role": "care_manager",
    "email": "dana@neuroflow.com", "password": "demo-password",
    "phone": "206-555-0198",
})
ramon = post("/providers", {
    "name": "Dr. Ramon Ortiz", "role": "psychiatric_consultant",
    "email": "ramon@neuroflow.com", "password": "demo-password",
    "phone": "206-555-0231",
})
lena = post("/providers", {
    "name": "Dr. Lena Fischer", "role": "primary_care_provider",
    "email": "lena@neuroflow.com", "phone": "206-555-0277",
})

RIVERSIDE = "riverside-family-health"
EASTGATE = "eastgate-community-clinic"


def enroll(*, mrn, name, dob, enrolled, clinic, care_manager, primary,
           secondary=None, payer="Medicaid", consultant=None, race=None):
    patient = post("/patients", {
        "mrn": mrn, "name": name, "payer": payer, "date_of_birth": dob,
        "consent_date": enrolled, "enrollment_date": enrolled,
        "race_ethnicity": race,
    })
    episode = post("/episodes", {
        "patient_id": patient["patient_id"], "start_date": enrolled,
        "primary_diagnosis": primary, "secondary_diagnosis": secondary,
    })
    post("/care-team-assignments", {
        "patient_id": patient["patient_id"], "provider_id": care_manager["provider_id"],
        "role": "care_manager", "service_begin_date": enrolled,
    })
    post("/care-team-assignments", {
        "patient_id": patient["patient_id"], "provider_id": lena["provider_id"],
        "role": "primary_care_provider", "service_begin_date": enrolled,
    })
    if consultant:
        post("/care-team-assignments", {
            "patient_id": patient["patient_id"], "provider_id": consultant["provider_id"],
            "role": "psychiatric_consultant", "service_begin_date": enrolled,
        })
    post("/clinic-assignments", {
        "patient_id": patient["patient_id"], "clinic_id": clinic,
        "is_primary": True, "service_begin_date": enrolled,
    })
    return patient, episode


def visit(patient, episode, ctype, when, minutes, scores=None, notes=None,
          location="in_clinic", provider=None, **extra):
    return post("/contacts", {
        "patient_id": patient["patient_id"],
        "episode_id": episode["episode_id"] if episode else None,
        "provider_id": (provider or priya)["provider_id"],
        "contact_type": ctype, "contact_date": when,
        "location": location, "duration_minutes": minutes, "notes": notes,
        "scores": [{"measure_type": m, "score_value": v} for m, v in (scores or [])],
        **extra,
    })


def review(patient, when, minutes, notes, forwarded=True, flag_next=False, reason=None):
    return post("/consultations", {
        "patient_id": patient["patient_id"], "provider_id": ramon["provider_id"],
        "consultation_date": when, "duration_minutes": minutes,
        "recommendations_forwarded": forwarded, "flagged_for_next_review": flag_next,
        "flag_reason": reason, "notes": notes,
    })


print("Seeding demo data…")

# ---------------------------------------------------------------------------
# 1. Grace Liu — long, successful depression course. Still active in relapse
#    prevention. Her baseline is in the PREVIOUS calendar year, so she is
#    also DRR-eligible with a fully closed follow-up window.
# ---------------------------------------------------------------------------
grace, grace_ep = enroll(
    mrn="MRN-40119", name="Grace Liu", dob="1986-03-14", enrolled=months_ago(14, 8),
    clinic=RIVERSIDE, care_manager=priya, primary="depression", consultant=ramon,
    race=["asian"], payer="Medicaid",
)
visit(grace, grace_ep, "initial_assessment", months_ago(14, 9), 50, [("PHQ9", 20), ("GAD7", 11)],
      notes="Intake. Six months of low mood, poor sleep, withdrawal from friends. "
            "Agreed to behavioral activation and weekly outreach.")
visit(grace, grace_ep, "follow_up", months_ago(13, 10), 30, [("PHQ9", 18)],
      notes="Started activity scheduling. Sleep still poor.")
review(grace, months_ago(13, 14), 15,
       "Reviewed at case conference. Agreed with starting sertraline 50 mg; PCP notified.")
visit(grace, grace_ep, "follow_up", months_ago(12, 12), 30, [("PHQ9", 15)],
      notes="Sertraline started. Tolerating well.")
visit(grace, grace_ep, "follow_up", months_ago(11, 9), 30, [("PHQ9", 12), ("GAD7", 8)],
      notes="Mood lifting. Back to walking group twice a week.")
visit(grace, grace_ep, "follow_up", months_ago(10, 14), 25, [("PHQ9", 9)],
      notes="Continued improvement.")
visit(grace, grace_ep, "follow_up", months_ago(8, 11), 25, [("PHQ9", 6)],
      notes="Response achieved. Discussed what maintenance looks like.")
visit(grace, grace_ep, "follow_up", months_ago(6, 10), 25, [("PHQ9", 4), ("GAD7", 3)],
      notes="Remission range. Beginning relapse prevention planning.")
visit(grace, grace_ep, "relapse_prevention_plan", months_ago(4, 15), 35, [("PHQ9", 3)],
      notes="Relapse prevention plan completed and signed. Copy to patient and PCP.",
      other_treatments="Walking group twice weekly; sertraline 50 mg daily",
      personal_warning_signs="Sleeping past 10am; cancelling plans two weeks running; "
                             "letting mail pile up",
      stress_reduction_plan="Daily 20-minute walk; Sunday call with sister; "
                            "book club Thursdays",
      additional_comments="Patient articulated her own warning signs unprompted — good insight.",
      medications_confirmation="confirmed_with_patient")
visit(grace, grace_ep, "follow_up", months_ago(2, 12), 20, [("PHQ9", 4)],
      notes="Maintenance check. Doing well.", location="phone")
visit(grace, grace_ep, "follow_up", days_ago(11), 20, [("PHQ9", 3), ("GAD7", 2)],
      notes="Maintenance check. Stable, engaged with plan.", location="phone")
post("/medications", {"patient_id": grace["patient_id"], "medication_key": "sertraline",
                      "dose": "50 mg", "frequency": "daily", "recorded_by": "Priya Nandakumar"})
post("/profile-entries", {"patient_id": grace["patient_id"], "section": "social_environmental",
                          "sub_field": "social_support", "value": "Close with sister; active book club",
                          "recorded_date": months_ago(14, 9), "recorded_by": "Priya Nandakumar"})
post("/profile-entries", {"patient_id": grace["patient_id"], "section": "behavioral_health",
                          "sub_field": "treatment_goals",
                          "value": "Return to walking group and regular sleep schedule",
                          "recorded_date": months_ago(14, 9)})
post("/profile-entries", {"patient_id": grace["patient_id"], "section": "behavioral_health",
                          "sub_field": "treatment_goals",
                          "value": "Maintain gains; stay in remission through the winter",
                          "recorded_date": months_ago(4, 15),
                          "context": "Updated at relapse prevention planning"})

# ---------------------------------------------------------------------------
# 2. Aisha Rahman — dual diagnosis, anxiety primary. Two trend graphs, with
#    the secondary deliberately outside the headline outcome rates.
# ---------------------------------------------------------------------------
aisha, aisha_ep = enroll(
    mrn="MRN-40204", name="Aisha Rahman", dob="1993-11-02", enrolled=months_ago(10, 5),
    clinic=RIVERSIDE, care_manager=priya, primary="anxiety", secondary="depression",
    consultant=ramon, payer="Commercial — Premera", race=["middle_eastern_or_north_african"],
)
visit(aisha, aisha_ep, "initial_assessment", months_ago(10, 6), 55, [("GAD7", 17), ("PHQ9", 14)],
      notes="Intake. Panic symptoms at work, constant worry, avoiding meetings. "
            "Anxiety is the primary driver; low mood appears secondary.")
visit(aisha, aisha_ep, "follow_up", months_ago(9, 8), 30, [("GAD7", 15), ("PHQ9", 13)],
      notes="Began breathing retraining and worry postponement.")
visit(aisha, aisha_ep, "follow_up", months_ago(8, 6), 30, [("GAD7", 12), ("PHQ9", 11)],
      notes="Using skills at work. One panic episode this month, shorter than usual.")
review(aisha, months_ago(8, 12), 20,
       "Case reviewed. Anxiety improving with CBT alone; hold on medication for now. "
       "Re-review if GAD-7 plateaus above 10.")
visit(aisha, aisha_ep, "follow_up", months_ago(6, 7), 30, [("GAD7", 9), ("PHQ9", 9)],
      notes="Meaningful improvement. Attending meetings again.")
aisha_referral = post("/referrals", {
    "patient_id": aisha["patient_id"],
    "referred_by_provider_id": priya["provider_id"],
    "referred_to": "Riverside Counseling Collective",
    "referral_date": months_ago(6, 7),
    "reason": "Ongoing individual CBT after graduation from CoCM"})
# Close out its follow-up reminder: a care manager would have confirmed this
# months ago, and leaving it open would show a nonsensical 150-day-overdue
# row on the landing page.
for reminder in client.get("/reminders", params={"patient_id": aisha["patient_id"]},
                           headers=H).json():
    if reminder["referral_id"] == aisha_referral["referral_id"]:
        patch(f"/reminders/{reminder['reminder_id']}", {"status": "completed"})
visit(aisha, aisha_ep, "follow_up", months_ago(4, 9), 25, [("GAD7", 6), ("PHQ9", 7)],
      notes="Response achieved on GAD-7.", location="virtual")
visit(aisha, aisha_ep, "follow_up", months_ago(2, 10), 25, [("GAD7", 4), ("PHQ9", 6)],
      notes="Remission range on anxiety. Mood also improved.", location="virtual")
visit(aisha, aisha_ep, "relapse_prevention_plan", days_ago(26), 30, [("GAD7", 4)],
      notes="Relapse prevention plan completed.",
      other_treatments="Individual CBT at Riverside Counseling Collective",
      personal_warning_signs="Avoiding meetings; checking email late at night; "
                             "chest tightness returning",
      stress_reduction_plan="Morning breathing practice; hard stop on email at 7pm; "
                            "Saturday hikes",
      additional_comments="Plan shared with her therapist with consent.",
      medications_confirmation="deferred")
visit(aisha, aisha_ep, "follow_up", days_ago(9), 20, [("GAD7", 3), ("PHQ9", 5)],
      notes="Maintenance check. Stable.", location="phone")
post("/profile-entries", {"patient_id": aisha["patient_id"], "section": "substance_use",
                          "sub_field": "alcohol", "value": "2-3 drinks per week, no escalation",
                          "recorded_date": months_ago(10, 6)})
post("/profile-entries", {"patient_id": aisha["patient_id"], "section": "social_environmental",
                          "sub_field": "employment",
                          "value": "Full-time software role; high-pressure team",
                          "recorded_date": months_ago(10, 6),
                          "context": "Identified as primary stressor at intake"})

# ---------------------------------------------------------------------------
# 3. Tom Becker — depression, improving slowly. Reviewed by the consultant,
#    so he does NOT count as "not improving without a consultation".
# ---------------------------------------------------------------------------
tom, tom_ep = enroll(
    mrn="MRN-40388", name="Tom Becker", dob="1972-06-30", enrolled=months_ago(5, 12),
    clinic=EASTGATE, care_manager=dana, primary="depression", consultant=ramon,
    payer="Medicare", race=["white"],
)
visit(tom, tom_ep, "initial_assessment", months_ago(5, 13), 50, [("PHQ9", 22)],
      notes="Intake. Severe symptoms following job loss. Denies suicidal ideation. "
            "Lives alone.", provider=dana)
visit(tom, tom_ep, "follow_up", months_ago(4, 14), 30, [("PHQ9", 20)],
      notes="Minimal change. Struggling to get out of the house.", provider=dana,
      discuss_with_psychiatric_consultant=True,
      notes_for_consultant="PHQ-9 22 → 20 after four weeks of behavioral activation. "
                           "Lives alone with limited support. Medication options?")
review(tom, months_ago(4, 9), 25,
       "Reviewed. Start sertraline 50 mg, titrate to 100 mg at four weeks if tolerated. "
       "Watch for activation. Re-review in eight weeks if PHQ-9 remains above 15.")
visit(tom, tom_ep, "follow_up", months_ago(3, 15), 30, [("PHQ9", 17)],
      notes="Sertraline started, now at 100 mg. Some improvement in sleep.", provider=dana)
visit(tom, tom_ep, "care_team_collaboration", months_ago(3, 20), 15,
      notes="Coordinated with Dr. Fischer on titration and lab follow-up. Patient not present.",
      provider=dana, location="phone")
visit(tom, tom_ep, "follow_up", months_ago(2, 16), 30, [("PHQ9", 15)],
      notes="Gradual improvement. Attending a weekly job-seekers group.", provider=dana)
review(tom, months_ago(2, 6), 20,
       "Second review. Partial response. Continue sertraline 100 mg; consider augmentation "
       "if PHQ-9 stalls above 12 at next review.")
visit(tom, tom_ep, "follow_up", months_ago(1, 14), 30, [("PHQ9", 13)],
      notes="Continued slow improvement.", provider=dana)
visit(tom, tom_ep, "follow_up", days_ago(13), 30, [("PHQ9", 12)],
      notes="Steady. Discussed pacing and realistic weekly goals.", provider=dana)
post("/medications", {"patient_id": tom["patient_id"], "medication_key": "sertraline",
                      "dose": "100 mg", "frequency": "daily", "recorded_by": "Dana Whitfield"})
post("/medications", {"patient_id": tom["patient_id"], "medication_name": "Lisinopril",
                      "dose": "10 mg", "frequency": "daily",
                      "recorded_by": "Dana Whitfield"})
post("/profile-entries", {"patient_id": tom["patient_id"], "section": "medical_profile",
                          "sub_field": "active_medical_conditions",
                          "value": "Hypertension, well controlled",
                          "recorded_date": months_ago(5, 13)})
post("/profile-entries", {"patient_id": tom["patient_id"], "section": "social_environmental",
                          "sub_field": "living_situation", "value": "Lives alone; rents an apartment",
                          "recorded_date": months_ago(5, 13)})
post("/profile-entries", {"patient_id": tom["patient_id"], "section": "social_environmental",
                          "sub_field": "employment", "value": "Unemployed since January; actively looking",
                          "recorded_date": months_ago(5, 13)})
post("/profile-entries", {"patient_id": tom["patient_id"], "section": "social_environmental",
                          "sub_field": "employment",
                          "value": "Started part-time warehouse work",
                          "recorded_date": days_ago(13),
                          "context": "Reported at most recent visit"})

# ---------------------------------------------------------------------------
# 4. Robert Ellis — flagged for review and NOT yet reviewed. This is what
#    puts CONSIDER on the caseload and drives the "not improving without a
#    psychiatric consultation" column.
# ---------------------------------------------------------------------------
robert, robert_ep = enroll(
    mrn="MRN-40455", name="Robert Ellis", dob="1965-01-19", enrolled=days_ago(52),
    clinic=EASTGATE, care_manager=dana, primary="depression", payer="Medicaid",
    race=["black_or_african_american"],
)
visit(robert, robert_ep, "contact_attempt", days_ago(50), 5,
      notes="Left voicemail.", provider=dana, location="phone")
visit(robert, robert_ep, "contact_attempt", days_ago(45), 5,
      notes="Second voicemail. Sent letter.", provider=dana, location="phone")
visit(robert, robert_ep, "initial_assessment", days_ago(38), 45, [("PHQ9", 21)],
      notes="Reached on third attempt. Severe symptoms, chronic back pain, ambivalent "
            "about treatment. Agreed to a trial of weekly calls.", provider=dana)
visit(robert, robert_ep, "follow_up", days_ago(19), 30, [("PHQ9", 20)],
      notes="Little change. Pain limiting activity. Reluctant to consider medication.",
      provider=dana, discuss_with_psychiatric_consultant=True,
      notes_for_consultant="PHQ-9 21 → 20 over five weeks. Chronic pain is a major barrier "
                           "and he is medication-averse. Looking for guidance on approach "
                           "and whether pain management referral should come first.")
post("/profile-entries", {"patient_id": robert["patient_id"], "section": "medical_profile",
                          "sub_field": "chronic_pain",
                          "value": "Chronic lower back pain, 8 years, limits standing to ~20 min",
                          "recorded_date": days_ago(38)})
post("/profile-entries", {"patient_id": robert["patient_id"], "section": "safety_and_risk",
                          "sub_field": "suicide_risk",
                          "value": "Passive thoughts of not wanting to wake up; no plan or intent. "
                                   "Safety plan reviewed.",
                          "recorded_date": days_ago(38),
                          "context": "PHQ-9 item 9 endorsed at 1"})
post("/profile-entries", {"patient_id": robert["patient_id"], "section": "safety_and_risk",
                          "sub_field": "safety_plan",
                          "value": "Crisis line saved in phone; nephew is emergency contact",
                          "recorded_date": days_ago(38)})

# ---------------------------------------------------------------------------
# 5. Sofia Petrov — anxiety, mid-course and improving.
# ---------------------------------------------------------------------------
sofia, sofia_ep = enroll(
    mrn="MRN-40512", name="Sofia Petrov", dob="1998-08-24", enrolled=months_ago(3, 6),
    clinic=RIVERSIDE, care_manager=priya, primary="anxiety", payer="Commercial — Aetna",
    race=["white"],
)
visit(sofia, sofia_ep, "initial_assessment", months_ago(3, 7), 45, [("GAD7", 16), ("PHQ9", 8)],
      notes="Intake. Health anxiety and frequent reassurance-seeking. Sleep onset difficulty.")
visit(sofia, sofia_ep, "follow_up", months_ago(2, 8), 30, [("GAD7", 13)],
      notes="Reduced checking behaviors. Practicing tolerating uncertainty.")
visit(sofia, sofia_ep, "follow_up", months_ago(1, 9), 30, [("GAD7", 11)], location="virtual",
      notes="Continued progress. Sleep improving.")
visit(sofia, sofia_ep, "follow_up", days_ago(7), 30, [("GAD7", 9), ("PHQ9", 5)],
      notes="Good engagement. Down to one reassurance call per week.", location="virtual")

# ---------------------------------------------------------------------------
# 6. Daniel Osei — PTSD. Shows a measure the registry tracks but deliberately
#    does not score (no confirmed PCL-5 threshold).
# ---------------------------------------------------------------------------
daniel, daniel_ep = enroll(
    mrn="MRN-40587", name="Daniel Osei", dob="1989-04-05", enrolled=months_ago(2, 20),
    clinic=EASTGATE, care_manager=dana, primary="ptsd", consultant=ramon, payer="Medicaid",
    race=["black_or_african_american"],
)
visit(daniel, daniel_ep, "initial_assessment", months_ago(2, 21), 55, [("PCL5", 52)],
      notes="Intake. Motor vehicle collision 14 months ago. Nightmares, avoidance of driving, "
            "hypervigilance.", provider=dana)
review(daniel, months_ago(2, 26), 20,
       "Reviewed. Recommend prazosin 1 mg at bedtime for nightmares and referral for "
       "trauma-focused therapy. Not a candidate for benzodiazepines.")
visit(daniel, daniel_ep, "follow_up", months_ago(1, 22), 30, [("PCL5", 47)],
      notes="Prazosin started. Nightmares less frequent.", provider=dana)
visit(daniel, daniel_ep, "follow_up", days_ago(15), 30, [("PCL5", 44)],
      notes="Driving short distances again. Still avoiding the highway.", provider=dana)
post("/medications", {"patient_id": daniel["patient_id"], "medication_key": "prazosin",
                      "dose": "2 mg", "frequency": "at bedtime", "recorded_by": "Dana Whitfield"})
post("/referrals", {"patient_id": daniel["patient_id"],
                    "referred_by_provider_id": dana["provider_id"],
                    "referred_to": "Eastgate Trauma Recovery Program",
                    "referral_date": months_ago(2, 26),
                    "reason": "Trauma-focused CBT"})

# ---------------------------------------------------------------------------
# 7. Chloe Martin — pediatric anxiety on the SCARED, also unscored.
# ---------------------------------------------------------------------------
chloe, chloe_ep = enroll(
    mrn="MRN-40601", name="Chloe Martin", dob=months_ago(14 * 12 + 2, 12), enrolled=months_ago(2, 2),
    clinic=RIVERSIDE, care_manager=priya, primary="anxiety", payer="Medicaid",
    race=["hispanic_or_latino"],
)
visit(chloe, chloe_ep, "initial_assessment", months_ago(2, 3), 50, [("SCARED", 38)],
      notes="Intake with mother present. School refusal two mornings a week, "
            "somatic complaints before school.")
visit(chloe, chloe_ep, "follow_up", months_ago(1, 4), 30, [("SCARED", 33)],
      notes="Graded return-to-school plan agreed with the school counselor.")
visit(chloe, chloe_ep, "follow_up", days_ago(17), 30, [("SCARED", 29)],
      notes="Attending five mornings this week. Mother reports fewer stomach aches.")
post("/profile-entries", {"patient_id": chloe["patient_id"], "section": "social_environmental",
                          "sub_field": "social_support",
                          "value": "Lives with mother and grandmother; both engaged in care",
                          "recorded_date": months_ago(2, 3)})

# ---------------------------------------------------------------------------
# 8. Nina Alvarez — brand-new enrollment. Her appointment reminder is coming
#    due, which is what the Reminders landing page is for.
# ---------------------------------------------------------------------------
nina, nina_ep = enroll(
    mrn="MRN-40644", name="Nina Alvarez", dob="2001-12-11", enrolled=days_ago(16),
    clinic=RIVERSIDE, care_manager=priya, primary="depression", payer="Medicaid",
    race=["hispanic_or_latino"],
)
visit(nina, nina_ep, "initial_assessment", days_ago(14), 50, [("PHQ9", 17), ("GAD7", 10)],
      notes="Intake. Postpartum onset four months ago. Supportive partner. "
            "Sleep fragmented by infant. Agreed to weekly contact.")
post("/profile-entries", {"patient_id": nina["patient_id"], "section": "medical_profile",
                          "sub_field": "pregnancy_status",
                          "value": "Postpartum, four months",
                          "recorded_date": days_ago(14)})

# ---------------------------------------------------------------------------
# 9-11. Completed episodes. Two closed this calendar year (so Completed
#       Episode Statistics has a cohort) and one last year. Their PHQ-9
#       baselines sit in the previous calendar year, making them DRR-eligible
#       with long-closed follow-up windows.
# ---------------------------------------------------------------------------
maria, maria_ep = enroll(
    mrn="MRN-39840", name="Maria Delgado", dob="1979-09-08", enrolled=months_ago(17, 4),
    clinic=RIVERSIDE, care_manager=priya, primary="depression", consultant=ramon,
    payer="Medicaid", race=["hispanic_or_latino"],
)
visit(maria, maria_ep, "initial_assessment", months_ago(17, 5), 50, [("PHQ9", 19)],
      notes="Intake. Depression following a bereavement.")
visit(maria, maria_ep, "follow_up", months_ago(16, 6), 30, [("PHQ9", 16)])
visit(maria, maria_ep, "follow_up", months_ago(14, 8), 30, [("PHQ9", 11)])
review(maria, months_ago(14, 12), 15, "Reviewed. Progressing well with counselling alone.")
visit(maria, maria_ep, "follow_up", months_ago(12, 7), 30, [("PHQ9", 7)],
      notes="Response achieved.")
visit(maria, maria_ep, "follow_up", months_ago(11, 9), 25, [("PHQ9", 4)],
      notes="Remission.")
visit(maria, maria_ep, "relapse_prevention_plan", months_ago(10, 10), 30, [("PHQ9", 3)],
      notes="Relapse prevention plan completed.",
      other_treatments="Bereavement group, monthly",
      personal_warning_signs="Withdrawing from the group; sleeping during the day",
      stress_reduction_plan="Weekly walks with a neighbour; monthly group",
      medications_confirmation="confirmed_in_medical_record")
visit(maria, maria_ep, "follow_up", months_ago(8, 12), 20, [("PHQ9", 3)], location="phone",
      notes="Maintenance check. Stable.")
visit(maria, maria_ep, "follow_up", months_ago(6, 15), 20, [("PHQ9", 2)], location="phone",
      notes="Final maintenance check before graduation. Plan reviewed; she knows how to "
            "get back in touch.")
patch(f"/episodes/{maria_ep['episode_id']}",
      {"end_date": months_ago(5, 20), "end_reason": "achieved_goals"})
patch(f"/patients/{maria['patient_id']}", {"deactivation_date": months_ago(5, 20)})

walter, walter_ep = enroll(
    mrn="MRN-39912", name="Walter Cheng", dob="1958-02-27", enrolled=months_ago(15, 10),
    clinic=EASTGATE, care_manager=dana, primary="anxiety", payer="Medicare", race=["asian"],
)
visit(walter, walter_ep, "initial_assessment", months_ago(15, 11), 45, [("GAD7", 14)],
      notes="Intake. Generalised worry, mostly financial.", provider=dana)
visit(walter, walter_ep, "follow_up", months_ago(14, 13), 30, [("GAD7", 12)], provider=dana)
visit(walter, walter_ep, "contact_attempt", months_ago(13, 15), 5, provider=dana, location="phone")
visit(walter, walter_ep, "contact_attempt", months_ago(12, 16), 5, provider=dana, location="phone")
patch(f"/episodes/{walter_ep['episode_id']}",
      {"end_date": months_ago(11, 2), "end_reason": "not_engaged"})
patch(f"/patients/{walter['patient_id']}", {"deactivation_date": months_ago(11, 2)})

frank, frank_ep = enroll(
    mrn="MRN-40021", name="Frank Doyle", dob="1970-07-16", enrolled=months_ago(13, 6),
    clinic=EASTGATE, care_manager=dana, primary="depression", consultant=ramon,
    payer="Commercial — Regence", race=["white"],
)
visit(frank, frank_ep, "initial_assessment", months_ago(13, 7), 50, [("PHQ9", 18)],
      notes="Intake. Depression with alcohol use as a complicating factor.", provider=dana)
visit(frank, frank_ep, "follow_up", months_ago(12, 9), 30, [("PHQ9", 15)], provider=dana)
review(frank, months_ago(12, 14), 20,
       "Reviewed. Address alcohol use alongside mood; recommend AUDIT-C monitoring at each visit.")
visit(frank, frank_ep, "follow_up", months_ago(10, 11), 30, [("PHQ9", 12)], provider=dana,
      notes="Cut back drinking. Mood following.")
visit(frank, frank_ep, "follow_up", months_ago(8, 12), 30, [("PHQ9", 10)], provider=dana)
patch(f"/episodes/{frank_ep['episode_id']}",
      {"end_date": months_ago(6, 4), "end_reason": "patient_choice"})
patch(f"/patients/{frank['patient_id']}", {"deactivation_date": months_ago(6, 4)})
post("/profile-entries", {"patient_id": frank["patient_id"], "section": "substance_use",
                          "sub_field": "alcohol",
                          "value": "6-8 drinks most evenings at intake",
                          "recorded_date": months_ago(13, 7)})
post("/profile-entries", {"patient_id": frank["patient_id"], "section": "substance_use",
                          "sub_field": "alcohol", "value": "Down to 2-3 drinks on weekends only",
                          "recorded_date": months_ago(10, 11),
                          "context": "Self-reported; sustained over two months"})

# ---------------------------------------------------------------------------
print("\nDemo data seeded.\n")
print("Sign in at http://localhost:5173 as any of:")
print(f"  Supervisor    {SUPERVISOR_EMAIL} / {SUPERVISOR_PASSWORD}")
print("  Care manager  priya@neuroflow.com / demo-password   (6 active patients)")
print("  Care manager  dana@neuroflow.com  / demo-password   (3 active patients)")
print("  Consultant    ramon@neuroflow.com / demo-password")
print()
print(f"Today is {TODAY.isoformat()}. Notes on what each screen will show:")
print("  Active Patients  — 8 patients, most recent scores within ~2 weeks so almost")
print("                     nothing is flagged stale; Robert Ellis reads CONSIDER.")
print("  Reminders        — a realistic mix of upcoming and slightly overdue outreach.")
print(f"  DRR Report       — run it for {TODAY.year - 1}: this year's baselines cannot have a")
print("                     closed 4-8 month window yet, which is correct, not a bug.")
print(f"  Completed Episodes — {TODAY.year} has a cohort; so does {TODAY.year - 1}.")
print("  Quality Metrics  — activity in every one of the twelve months.")
