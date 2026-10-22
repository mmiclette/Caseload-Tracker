"""
ContactService.record_contact is the Phase 2 replacement for Phase 1's
EpisodeService.add_symptom_score — this file carries forward the equivalent
baseline coverage from the old test_episode_service.py tests (now exercised
through a real Contact), plus new coverage for the cascades and validation
rules specific to Contact: the RPP-cascade, the discuss-with-consultant
flag, attempt_number sequencing, and the two ValueError guards.
"""

from datetime import date

import pytest

from app.models.enums import ContactType, MeasureType, TreatmentStatusEnum
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService


def make_patient(db_session, mrn="MRN-CS-1"):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Contact Service Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 2),
        )
    )


def test_recording_a_contact_with_scores_sets_episode_baseline(db_session):
    patient = make_patient(db_session)
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 2, 1)
    )
    service = ContactService(db_session)

    service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 2, 1),
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 18}],
    )
    service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 2, 15),
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 10}],
    )

    refreshed = service.episode_service.episodes.get_by_id(episode.episode_id)
    assert refreshed.baseline_measure_type == MeasureType.PHQ9
    assert refreshed.baseline_score == 18
    assert refreshed.baseline_date == date(2026, 2, 1)


def test_backdated_score_still_becomes_baseline(db_session):
    patient = make_patient(db_session, mrn="MRN-CS-2")
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 3, 1)
    )
    service = ContactService(db_session)

    # Enter the later contact first, then a backdated correction.
    service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 3, 20),
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 12}],
    )
    service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 3, 5),
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 20}],
    )

    refreshed = service.episode_service.episodes.get_by_id(episode.episode_id)
    assert refreshed.baseline_score == 20
    assert refreshed.baseline_date == date(2026, 3, 5)


def test_rpp_contact_cascades_treatment_status(db_session):
    patient = make_patient(db_session, mrn="MRN-CS-3")
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 6, 1)
    )
    service = ContactService(db_session)

    service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.RELAPSE_PREVENTION_PLAN,
        contact_date=date(2026, 7, 1),
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 3}],
    )

    current = service.episode_service.get_current_status(patient.patient_id)
    assert current.status == TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN
    assert current.status_changed_date == date(2026, 7, 1)


def test_repeated_rpp_contacts_do_not_duplicate_status_history(db_session):
    patient = make_patient(db_session, mrn="MRN-CS-4")
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 6, 1)
    )
    service = ContactService(db_session)

    for contact_date in [date(2026, 7, 1), date(2026, 7, 29), date(2026, 8, 26)]:
        service.record_contact(
            patient_id=patient.patient_id,
            episode_id=episode.episode_id,
            contact_type=ContactType.RELAPSE_PREVENTION_PLAN,
            contact_date=contact_date,
            scores=[{"measure_type": MeasureType.PHQ9, "score_value": 3}],
        )

    history = service.episode_service.statuses.list_by_patient(patient.patient_id)
    assert [h.status for h in history] == [
        TreatmentStatusEnum.ACTIVE_TREATMENT,
        TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN,
    ]


def test_discuss_with_consultant_sets_needs_psychiatric_review_flag(db_session):
    patient = make_patient(db_session, mrn="MRN-CS-5")
    service = ContactService(db_session)
    assert patient.needs_psychiatric_review is False

    service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 6, 1),
        discuss_with_psychiatric_consultant=True,
    )

    refreshed = service.patients.get_by_id(patient.patient_id)
    assert refreshed.needs_psychiatric_review is True


def test_discuss_with_consultant_never_clears_an_already_set_flag(db_session):
    """The checkbox only ever turns the flag ON — only a Consultation clears it."""
    patient = make_patient(db_session, mrn="MRN-CS-6")
    service = ContactService(db_session)
    service.patients.update(patient, needs_psychiatric_review=True)

    service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 6, 1),
        discuss_with_psychiatric_consultant=False,
    )

    refreshed = service.patients.get_by_id(patient.patient_id)
    assert refreshed.needs_psychiatric_review is True


def test_attempt_number_increments_across_consecutive_attempts(db_session):
    patient = make_patient(db_session, mrn="MRN-CS-7")
    service = ContactService(db_session)

    first = service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 6, 1),
    )
    second = service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 6, 8),
    )

    assert first.attempt_number == 1
    assert second.attempt_number == 2


def test_attempt_number_resets_after_a_completed_contact(db_session):
    patient = make_patient(db_session, mrn="MRN-CS-8")
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 6, 1)
    )
    service = ContactService(db_session)

    service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 6, 1),
    )
    service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 6, 8),
    )
    after_completed = service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 6, 15),
    )

    assert after_completed.attempt_number == 1


def test_contact_attempt_cannot_carry_scores(db_session):
    patient = make_patient(db_session, mrn="MRN-CS-9")
    service = ContactService(db_session)

    with pytest.raises(ValueError, match="contact_attempt cannot carry Symptom Scores"):
        service.record_contact(
            patient_id=patient.patient_id,
            contact_type=ContactType.CONTACT_ATTEMPT,
            contact_date=date(2026, 6, 1),
            scores=[{"measure_type": MeasureType.PHQ9, "score_value": 10}],
        )


def test_scores_require_an_episode_id(db_session):
    patient = make_patient(db_session, mrn="MRN-CS-10")
    service = ContactService(db_session)

    with pytest.raises(ValueError, match="Recording scores requires episode_id"):
        service.record_contact(
            patient_id=patient.patient_id,
            contact_type=ContactType.INITIAL_ASSESSMENT,
            contact_date=date(2026, 6, 1),
            scores=[{"measure_type": MeasureType.PHQ9, "score_value": 10}],
        )
