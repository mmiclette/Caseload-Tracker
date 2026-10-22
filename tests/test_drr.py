from datetime import date

from app.models.clinic_assignment import ClinicAssignment
from app.models.enums import ContactType, MeasureType
from app.models.patient import Patient
from app.repositories.clinic_assignment import ClinicAssignmentRepository
from app.repositories.patient import PatientRepository
from app.services.contact_service import ContactService
from app.services.drr import build_drr_report
from app.services.episode_service import EpisodeService


def make_patient(db_session, mrn):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="DRR Test Patient",
            payer="Medicaid",
            date_of_birth=date(1982, 9, 3),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def assign_clinic(db_session, patient, clinic_id, is_primary=True):
    ClinicAssignmentRepository(db_session).create(
        ClinicAssignment(
            patient_id=patient.patient_id,
            clinic_id=clinic_id,
            is_primary=is_primary,
            service_begin_date=date(2026, 1, 1),
        )
    )


def test_empty_year_returns_no_rows(db_session):
    rows = build_drr_report(db_session, 2026, as_of=date(2026, 12, 31))
    assert rows == []


def test_episode_excluded_while_follow_up_window_still_open(db_session):
    """as_of before baseline_date + 8 months means the outcome is unknown, not a failure."""
    patient = make_patient(db_session, "MRN-DRR-1")
    assign_clinic(db_session, patient, "drr-clinic-a")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 5),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 18}],
    )

    # Only 2 months after baseline -- the 4-8 month window hasn't even opened yet.
    rows = build_drr_report(db_session, 2026, as_of=date(2026, 3, 1))
    assert rows == []


def test_follow_up_completed_with_response_and_remission(db_session):
    patient = make_patient(db_session, "MRN-DRR-2")
    assign_clinic(db_session, patient, "drr-clinic-a")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 5),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 20}],
    )
    # 5 months after baseline, inside the 4-8 month window. >=50% reduction
    # from 20 -> 4 counts as response, and 4 < 5 also counts as remission.
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 6, 5),
        duration_minutes=30,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 4}],
    )

    rows = build_drr_report(db_session, 2026, as_of=date(2026, 10, 1))
    assert len(rows) == 1
    row = rows[0]
    assert row.clinic_id == "drr-clinic-a"
    assert row.index_episode_count == 1
    assert row.follow_up_phq9_count == 1
    assert row.follow_up_phq9_percentage == 100.0
    assert row.depression_remission_count == 1
    assert row.depression_response_count == 1


def test_follow_up_at_seven_months_counts(db_session):
    """
    Regression guard for the 2026-08-07 window correction (4-6 -> 4-8, per
    the CTMS's own Follow-Up PHQ-9 tooltip): a score 7 months after
    baseline is inside the window and must count. Under the old 4-6 rule
    this episode would have shown a missed follow-up.
    """
    patient = make_patient(db_session, "MRN-DRR-7MO")
    assign_clinic(db_session, patient, "drr-clinic-a")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 5),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 20}],
    )
    # 2026-08-05 is 7 months after the 2026-01-05 baseline: outside 4-6,
    # inside 4-8. 20 -> 3 is both a response and remission.
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 8, 5),
        duration_minutes=30,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 3}],
    )

    rows = build_drr_report(db_session, 2026, as_of=date(2026, 10, 1))
    assert len(rows) == 1
    assert rows[0].follow_up_phq9_count == 1
    assert rows[0].depression_response_count == 1
    assert rows[0].depression_remission_count == 1


def test_missing_follow_up_counts_against_every_rate(db_session):
    """No PHQ-9 recorded in the window -- follow-up, remission, and response all miss, denominator still counts."""
    patient = make_patient(db_session, "MRN-DRR-3")
    assign_clinic(db_session, patient, "drr-clinic-b")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 5),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 22}],
    )

    rows = build_drr_report(db_session, 2026, as_of=date(2026, 10, 1))
    assert len(rows) == 1
    row = rows[0]
    assert row.clinic_id == "drr-clinic-b"
    assert row.index_episode_count == 1
    assert row.follow_up_phq9_count == 0
    assert row.follow_up_phq9_percentage == 0.0
    assert row.depression_remission_count == 0
    assert row.depression_response_count == 0


def test_no_current_clinic_groups_as_unassigned(db_session):
    patient = make_patient(db_session, "MRN-DRR-4")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 5),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 15}],
    )

    rows = build_drr_report(db_session, 2026, as_of=date(2026, 10, 1))
    assert len(rows) == 1
    assert rows[0].clinic_id == "unassigned"


def test_baseline_outside_report_year_excluded(db_session):
    patient = make_patient(db_session, "MRN-DRR-5")
    assign_clinic(db_session, patient, "drr-clinic-a")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2025, 1, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2025, 1, 5),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 15}],
    )

    rows = build_drr_report(db_session, 2026, as_of=date(2026, 12, 31))
    assert rows == []
