from datetime import date

from app.models.enums import ContactType, EndReason, MeasureType
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService
from app.services.reporting import build_completed_episode_statistics


def make_patient(db_session, mrn):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Completed Episode Stats Test Patient",
            payer="Medicaid",
            date_of_birth=date(1990, 6, 15),
            consent_date=date(2025, 1, 1),
            enrollment_date=date(2025, 1, 1),
        )
    )


def test_no_completed_episodes_returns_zero_with_null_averages(db_session):
    stats = build_completed_episode_statistics(db_session, 2026)
    assert stats.year == 2026
    assert stats.total_completed_episodes == 0
    assert stats.avg_weeks_in_treatment is None
    assert stats.avg_contacts_per_episode is None
    assert stats.relapse_prevention_plan_count == 0
    assert stats.deactivation_reason_counts["not_recorded"] == 0
    assert stats.depression_response_denominator == 0


def test_open_episode_and_wrong_year_excluded(db_session):
    """An episode still open, or closed in a different year, isn't in the cohort."""
    patient_open = make_patient(db_session, "MRN-CES-OPEN")
    EpisodeService(db_session).create_episode(patient_id=patient_open.patient_id, start_date=date(2026, 1, 1))

    patient_other_year = make_patient(db_session, "MRN-CES-OTHERYEAR")
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(patient_id=patient_other_year.patient_id, start_date=date(2025, 1, 1))
    episode_service.update_episode(episode.episode_id, end_date=date(2025, 6, 1), end_reason=EndReason.ACHIEVED_GOALS)

    stats = build_completed_episode_statistics(db_session, 2026)
    assert stats.total_completed_episodes == 0


def test_weeks_in_treatment_and_contacts_and_rpp_and_deactivation_reason(db_session):
    patient = make_patient(db_session, "MRN-CES-1")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))

    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 1),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 20}],
    )
    # A contact_attempt should not count toward avg_contacts_per_episode.
    contact_service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 1, 8),
    )
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.RELAPSE_PREVENTION_PLAN,
        contact_date=date(2026, 2, 26),
        duration_minutes=30,
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 8}],
    )

    # 8 weeks (56 days) after start_date.
    episode_service.update_episode(
        episode.episode_id, end_date=date(2026, 2, 26), end_reason=EndReason.ACHIEVED_GOALS
    )

    stats = build_completed_episode_statistics(db_session, 2026)
    assert stats.total_completed_episodes == 1
    assert stats.avg_weeks_in_treatment == 8.0
    assert stats.avg_contacts_per_episode == 2.0
    assert stats.relapse_prevention_plan_count == 1
    assert stats.deactivation_reason_counts["achieved_goals"] == 1
    assert stats.deactivation_reason_counts["not_recorded"] == 0

    # >= 50% reduction from baseline 20 -> 8 counts as a PHQ-9 response.
    assert stats.depression_response_denominator == 1
    assert stats.depression_response_count == 1


def test_episode_closed_without_end_reason_counts_as_not_recorded(db_session):
    patient = make_patient(db_session, "MRN-CES-2")
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 3, 1))
    episode_service.update_episode(episode.episode_id, end_date=date(2026, 4, 1))

    stats = build_completed_episode_statistics(db_session, 2026)
    assert stats.deactivation_reason_counts["not_recorded"] == 1
    assert stats.deactivation_reason_counts["achieved_goals"] == 0


def test_ptsd_improvement_always_zero_pending_unconfirmed_threshold(db_session):
    """
    PCL-5 has no confirmed response threshold, so assess_score() always
    returns is_response=False for it — this must stay 0/denominator, not
    silently become 1 if someone "fixes" this without AIMS sign-off.
    """
    patient = make_patient(db_session, "MRN-CES-3")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)

    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 1),
        duration_minutes=45,
        scores=[{"measure_type": MeasureType.PCL5, "score_value": 60}],
    )
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 2, 1),
        duration_minutes=30,
        scores=[{"measure_type": MeasureType.PCL5, "score_value": 10}],
    )
    episode_service.update_episode(
        episode.episode_id, end_date=date(2026, 2, 15), end_reason=EndReason.ACHIEVED_GOALS
    )

    stats = build_completed_episode_statistics(db_session, 2026)
    assert stats.ptsd_improvement_denominator == 1
    assert stats.ptsd_improvement_count == 0
