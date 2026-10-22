"""
Phase 9 semantics, per the CTMS's confirmed field definitions
(docs/ctms-reference/README.md): care_team_collaboration contacts,
Consultation.duration_minutes, and the caseload-list score indicators.
"""

from datetime import date

import pytest

from app.models.enums import ConditionType, ContactType, MeasureType
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.consultation_service import ConsultationService
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService
from app.services.quality_metrics import build_quality_metrics
from app.services.reporting import build_active_patients_report
from app.services.time_tracker import build_monthly_time_tracker


def make_enrolled_patient(db_session, mrn="MRN-CTC-1"):
    patient = PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Collab Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id,
        start_date=date(2026, 1, 1),
        primary_diagnosis=ConditionType.DEPRESSION,
    )
    return patient, episode


def record(db_session, patient, episode, ctype, cdate, minutes=None, scores=None):
    return ContactService(db_session).record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ctype,
        contact_date=cdate,
        duration_minutes=minutes,
        scores=scores or [],
    )


def test_collaboration_cannot_carry_scores(db_session):
    patient, episode = make_enrolled_patient(db_session)
    with pytest.raises(ValueError, match="care_team_collaboration cannot carry"):
        record(
            db_session, patient, episode,
            ContactType.CARE_TEAM_COLLABORATION, date(2026, 1, 5), minutes=10,
            scores=[{"measure_type": MeasureType.PHQ9, "score_value": 10}],
        )


def test_collaboration_is_not_a_session_but_its_minutes_count(db_session):
    patient, episode = make_enrolled_patient(db_session)
    record(db_session, patient, episode, ContactType.INITIAL_ASSESSMENT, date(2026, 1, 5),
           minutes=45, scores=[{"measure_type": MeasureType.PHQ9, "score_value": 14}])
    record(db_session, patient, episode, ContactType.CARE_TEAM_COLLABORATION,
           date(2026, 1, 12), minutes=15)

    rows = build_active_patients_report(db_session, as_of=date(2026, 1, 31))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.session_count == 1  # the collaboration is not a session
    assert row.minutes_this_month == 60  # ... but its 15 minutes are billable

    tracker = {r.patient_id: r for r in build_monthly_time_tracker(db_session, date(2026, 1, 31))}
    assert tracker[patient.patient_id].total_minutes == 60


def test_collaboration_does_not_count_as_engagement(db_session):
    patient, episode = make_enrolled_patient(db_session, mrn="MRN-CTC-2")
    record(db_session, patient, episode, ContactType.CARE_TEAM_COLLABORATION,
           date(2026, 1, 12), minutes=15)

    jan = next(m for m in build_quality_metrics(db_session, date(2026, 1, 31))
               if (m.year, m.month) == (2026, 1))
    assert jan.caseload_size == 1
    assert jan.engagement_count == 0  # the patient was never actually reached


def test_collaboration_does_not_reset_attempt_counter_or_reminder_clock(db_session):
    patient, episode = make_enrolled_patient(db_session, mrn="MRN-CTC-3")
    a1 = record(db_session, patient, episode, ContactType.CONTACT_ATTEMPT, date(2026, 1, 5))
    record(db_session, patient, episode, ContactType.CARE_TEAM_COLLABORATION,
           date(2026, 1, 8), minutes=10)
    a2 = record(db_session, patient, episode, ContactType.CONTACT_ATTEMPT, date(2026, 1, 12))
    assert (a1.attempt_number, a2.attempt_number) == (1, 2)  # collab didn't reset to #1

    # No completed encounter yet, so the appointment reminder still keys off
    # enrollment (+7 days), not off the collaboration's date.
    from app.repositories.reminder import ReminderRepository
    reminder = ReminderRepository(db_session).get_pending_appointment_reminder(patient.patient_id)
    assert reminder.due_date == date(2026, 1, 8)  # enrollment 1/1 + 7


def test_consultation_minutes_count_toward_billing(db_session):
    patient, episode = make_enrolled_patient(db_session, mrn="MRN-CTC-4")
    record(db_session, patient, episode, ContactType.INITIAL_ASSESSMENT, date(2026, 1, 5),
           minutes=45, scores=[{"measure_type": MeasureType.PHQ9, "score_value": 14}])
    ConsultationService(db_session).record_consultation(
        patient_id=patient.patient_id,
        consultation_date=date(2026, 1, 20),
        duration_minutes=20,
        notes="Case reviewed in SCR.",
    )

    rows = build_active_patients_report(db_session, as_of=date(2026, 1, 31))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.minutes_this_month == 65  # 45 contact + 20 consultation

    tracker = {r.patient_id: r for r in build_monthly_time_tracker(db_session, date(2026, 1, 31))}
    assert tracker[patient.patient_id].total_minutes == 65


def test_minutes_this_month_matches_time_tracker(db_session):
    """
    Active Patients' "Minutes This Month" and the Monthly Time Tracker
    answer the same question and must apply the same rule: care-manager
    contacts (collaboration included) plus psychiatric consultations,
    with contact_attempt excluded. They disagreed until 2026-08-12 —
    Minutes This Month had no contact-type filter, so an attempt carrying
    minutes inflated it above the tracker.
    """
    patient, episode = make_enrolled_patient(db_session, mrn="MRN-CTC-MIN")
    record(db_session, patient, episode, ContactType.INITIAL_ASSESSMENT, date(2026, 1, 5),
           minutes=45, scores=[{"measure_type": MeasureType.PHQ9, "score_value": 14}])
    record(db_session, patient, episode, ContactType.CARE_TEAM_COLLABORATION,
           date(2026, 1, 8), minutes=15)
    # An attempt with minutes on it — the shape the contact form allows.
    record(db_session, patient, episode, ContactType.CONTACT_ATTEMPT, date(2026, 1, 9), minutes=5)
    ConsultationService(db_session).record_consultation(
        patient_id=patient.patient_id, consultation_date=date(2026, 1, 20), duration_minutes=20
    )

    as_of = date(2026, 1, 31)
    row = next(
        r
        for r in build_active_patients_report(db_session, as_of=as_of)
        if r.patient_id == patient.patient_id
    )
    tracker_row = next(
        r for r in build_monthly_time_tracker(db_session, as_of) if r.patient_id == patient.patient_id
    )
    january = next(m.minutes for m in tracker_row.months if (m.year, m.month) == (2026, 1))

    assert row.minutes_this_month == 45 + 15 + 20  # the attempt's 5 minutes are excluded
    assert row.minutes_this_month == january


def test_consultation_only_patient_appears_in_time_tracker(db_session):
    patient, _ = make_enrolled_patient(db_session, mrn="MRN-CTC-5")
    ConsultationService(db_session).record_consultation(
        patient_id=patient.patient_id,
        consultation_date=date(2026, 1, 20),
        duration_minutes=30,
    )
    tracker = {r.patient_id: r for r in build_monthly_time_tracker(db_session, date(2026, 1, 31))}
    assert tracker[patient.patient_id].total_minutes == 30


# --- caseload score indicators ------------------------------------------------


def test_score_cell_indicators(db_session):
    patient, episode = make_enrolled_patient(db_session, mrn="MRN-CTC-6")
    record(db_session, patient, episode, ContactType.INITIAL_ASSESSMENT, date(2026, 1, 5),
           minutes=45, scores=[{"measure_type": MeasureType.PHQ9, "score_value": 14}])

    # Single score, fresh (as_of 20 days later): gray-first rule, no asterisk, red band.
    rows = build_active_patients_report(db_session, as_of=date(2026, 1, 25))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.phq9_single_score is True
    assert row.phq9_stale is False
    assert row.phq9_last_color == "red"  # 14 with no improvement

    # Same score viewed 31+ days later: the staleness asterisk turns on.
    rows = build_active_patients_report(db_session, as_of=date(2026, 2, 10))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.phq9_stale is True

    # A second, improved score: not single anymore; 14 -> 7 is 50% improved -> yellow.
    record(db_session, patient, episode, ContactType.FOLLOW_UP, date(2026, 2, 12),
           minutes=30, scores=[{"measure_type": MeasureType.PHQ9, "score_value": 7}])
    rows = build_active_patients_report(db_session, as_of=date(2026, 2, 20))
    row = next(r for r in rows if r.patient_id == patient.patient_id)
    assert row.phq9_single_score is False
    assert row.phq9_stale is False
    assert row.phq9_last_color == "yellow"

    # GAD-7 never recorded: indicators stay None, and no color is invented.
    assert row.gad7_stale is None
    assert row.gad7_single_score is None
