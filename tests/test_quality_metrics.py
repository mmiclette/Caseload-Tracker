from datetime import date

from app.models.consultation import Consultation
from app.models.enums import ContactType, MeasureType
from app.models.patient import Patient
from app.repositories.consultation import ConsultationRepository
from app.repositories.patient import PatientRepository
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService
from app.services.quality_metrics import build_quality_metrics


def make_patient(db_session, mrn):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Quality Metrics Test Patient",
            payer="Medicaid",
            date_of_birth=date(1988, 4, 12),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def test_rolling_window_ends_on_as_of_month(db_session):
    months = build_quality_metrics(db_session, date(2026, 6, 15))
    assert len(months) == 12
    assert (months[-1].year, months[-1].month) == (2026, 6)
    assert (months[0].year, months[0].month) == (2025, 7)


def test_empty_caseload_month_has_zero_denominators_and_null_reach(db_session):
    months = build_quality_metrics(db_session, date(2026, 6, 15))
    june = months[-1]
    assert june.caseload_size == 0
    assert june.caseload_reach is None
    assert june.engagement_denominator == 0
    assert june.engagement_percentage == 0.0


def test_engagement_measures_completion_and_case_review_for_current_month(db_session):
    patient = make_patient(db_session, "MRN-QM-1")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 6, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 6, 5),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 18}],
    )
    ConsultationRepository(db_session).create(
        Consultation(patient_id=patient.patient_id, consultation_date=date(2026, 6, 10))
    )

    months = build_quality_metrics(db_session, date(2026, 6, 15))
    june = months[-1]

    assert june.caseload_size == 1
    assert june.engagement_count == 1
    assert june.engagement_denominator == 1
    assert june.engagement_percentage == 100.0
    assert june.measures_completion_count == 1
    assert june.psychiatric_case_review_count == 1
    assert june.psychiatric_case_review_denominator == 1


def test_contact_attempt_does_not_count_as_engagement(db_session):
    patient = make_patient(db_session, "MRN-QM-2")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 6, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 6, 5),
    )

    months = build_quality_metrics(db_session, date(2026, 6, 15))
    june = months[-1]
    assert june.caseload_size == 1
    assert june.engagement_count == 0


def test_depression_response_counted_in_the_month_of_the_comparison_score(db_session):
    patient = make_patient(db_session, "MRN-QM-3")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 6, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 6, 1),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 20}],
    )
    # >= 50% reduction from baseline 20 -> 8 counts as a PHQ-9 response.
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 6, 20),
        duration_minutes=30,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 8}],
    )

    months = build_quality_metrics(db_session, date(2026, 6, 15))
    june = months[-1]
    assert june.depression_response_denominator == 1
    assert june.depression_response_count == 1


def test_ptsd_improvement_always_zero_pending_unconfirmed_threshold(db_session):
    patient = make_patient(db_session, "MRN-QM-4")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 6, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 6, 1),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PCL5, "score_value": 60}],
    )
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 6, 20),
        duration_minutes=30,
        scores=[{"measure_type": MeasureType.PCL5, "score_value": 5}],
    )

    months = build_quality_metrics(db_session, date(2026, 6, 15))
    june = months[-1]
    assert june.ptsd_improvement_denominator == 1
    assert june.ptsd_improvement_count == 0


def test_episode_open_before_and_after_month_still_counts_toward_caseload(db_session):
    """An episode spanning the whole month (not started or ended within it) still puts the patient on caseload."""
    patient = make_patient(db_session, "MRN-QM-5")
    episode_service = EpisodeService(db_session)
    episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))

    months = build_quality_metrics(db_session, date(2026, 6, 15))
    june = months[-1]
    assert june.caseload_size == 1
