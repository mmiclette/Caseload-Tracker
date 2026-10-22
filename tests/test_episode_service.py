from datetime import date

from app.models.contact import Contact
from app.models.enums import ContactType, EndReason, MeasureType, TreatmentStatusEnum
from app.models.patient import Patient
from app.models.symptom_score import SymptomScore
from app.repositories.contact import ContactRepository
from app.repositories.patient import PatientRepository
from app.repositories.symptom_score import SymptomScoreRepository
from app.services.episode_service import EpisodeService


def make_contact(db_session, *, patient_id, episode_id, contact_date):
    """
    A SymptomScore row always belongs to a real Contact as of Phase 2 (see
    app/models/symptom_score.py — contact_id is NOT NULL). These
    recompute_baseline tests care about the score, not the contact, so this
    is a bare-minimum follow-up Contact just to satisfy the foreign key.
    """
    return ContactRepository(db_session).create(
        Contact(
            patient_id=patient_id,
            episode_id=episode_id,
            contact_type=ContactType.FOLLOW_UP,
            contact_date=contact_date,
        )
    )


def make_patient(db_session, mrn="MRN-EP-1"):
    repo = PatientRepository(db_session)
    return repo.create(
        Patient(
            mrn=mrn,
            name="Episode Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 2),
        )
    )


def test_create_episode_sets_active_treatment_status(db_session):
    patient = make_patient(db_session)
    service = EpisodeService(db_session)

    episode = service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 10))

    current_status = service.get_current_status(patient.patient_id)
    assert current_status is not None
    assert current_status.status == TreatmentStatusEnum.ACTIVE_TREATMENT
    assert current_status.episode_id == episode.episode_id


def test_transition_status_records_new_history_row(db_session):
    patient = make_patient(db_session, mrn="MRN-EP-4")
    service = EpisodeService(db_session)
    episode = service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 4, 1))

    service.transition_status(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        status=TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN,
        status_changed_date=date(2026, 5, 1),
    )

    history = service.statuses.list_by_patient(patient.patient_id)
    assert [h.status for h in history] == [
        TreatmentStatusEnum.ACTIVE_TREATMENT,
        TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN,
    ]
    current = service.get_current_status(patient.patient_id)
    assert current.status == TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN


def test_closing_episode_cascades_to_deactivated_status(db_session):
    """
    Setting end_date on an open episode is what the CTMS calls
    deactivating a patient — it should transition Treatment Status without
    a second explicit call.
    """
    patient = make_patient(db_session, mrn="MRN-EP-8")
    service = EpisodeService(db_session)
    episode = service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))

    updated = service.update_episode(
        episode.episode_id, end_date=date(2026, 4, 1), end_reason=EndReason.ACHIEVED_GOALS
    )

    assert updated.end_date == date(2026, 4, 1)
    current = service.get_current_status(patient.patient_id)
    assert current.status == TreatmentStatusEnum.DEACTIVATED
    assert current.status_changed_date == date(2026, 4, 1)


def test_closing_an_already_closed_episode_does_not_duplicate_status(db_session):
    patient = make_patient(db_session, mrn="MRN-EP-9")
    service = EpisodeService(db_session)
    episode = service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))

    service.update_episode(
        episode.episode_id, end_date=date(2026, 4, 1), end_reason=EndReason.ACHIEVED_GOALS
    )
    # A second update that touches end_reason only (end_date unchanged,
    # already set) should not add another deactivated row.
    service.update_episode(episode.episode_id, end_reason=EndReason.OTHER)

    history = service.statuses.list_by_patient(patient.patient_id)
    assert [h.status for h in history] == [
        TreatmentStatusEnum.ACTIVE_TREATMENT,
        TreatmentStatusEnum.DEACTIVATED,
    ]


def test_partial_update_without_end_date_does_not_cascade(db_session):
    patient = make_patient(db_session, mrn="MRN-EP-10")
    service = EpisodeService(db_session)
    episode = service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))

    service.update_episode(episode.episode_id, end_reason=EndReason.OTHER)

    history = service.statuses.list_by_patient(patient.patient_id)
    assert [h.status for h in history] == [TreatmentStatusEnum.ACTIVE_TREATMENT]


# --- recompute_baseline: as of Phase 2 this is the standalone baseline-
# bookkeeping unit, called by ContactService after it writes scores (see
# test_contact_service.py for the cascade-level coverage through a real
# Contact). These tests exercise the logic directly against the Symptom
# Score table, independent of how the rows got there. ---


def test_recompute_baseline_sets_from_first_score(db_session):
    patient = make_patient(db_session, mrn="MRN-EP-2")
    service = EpisodeService(db_session)
    episode = service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 2, 1))
    scores = SymptomScoreRepository(db_session)

    contact_1 = make_contact(
        db_session, patient_id=patient.patient_id, episode_id=episode.episode_id,
        contact_date=date(2026, 2, 1),
    )
    scores.create(
        SymptomScore(
            patient_id=patient.patient_id,
            episode_id=episode.episode_id,
            contact_id=contact_1.contact_id,
            measure_type=MeasureType.PHQ9,
            score_value=18,
            score_date=date(2026, 2, 1),
        )
    )
    service.recompute_baseline(episode.episode_id, MeasureType.PHQ9)
    contact_2 = make_contact(
        db_session, patient_id=patient.patient_id, episode_id=episode.episode_id,
        contact_date=date(2026, 2, 15),
    )
    scores.create(
        SymptomScore(
            patient_id=patient.patient_id,
            episode_id=episode.episode_id,
            contact_id=contact_2.contact_id,
            measure_type=MeasureType.PHQ9,
            score_value=10,
            score_date=date(2026, 2, 15),
        )
    )
    service.recompute_baseline(episode.episode_id, MeasureType.PHQ9)

    refreshed = service.episodes.get_by_id(episode.episode_id)
    assert refreshed.baseline_measure_type == MeasureType.PHQ9
    assert refreshed.baseline_score == 18
    assert refreshed.baseline_date == date(2026, 2, 1)


def test_recompute_baseline_uses_earliest_score_regardless_of_entry_order(db_session):
    patient = make_patient(db_session, mrn="MRN-EP-3")
    service = EpisodeService(db_session)
    episode = service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 3, 1))
    scores = SymptomScoreRepository(db_session)

    # Enter the later score first, then a score dated earlier than it.
    contact_1 = make_contact(
        db_session, patient_id=patient.patient_id, episode_id=episode.episode_id,
        contact_date=date(2026, 3, 20),
    )
    scores.create(
        SymptomScore(
            patient_id=patient.patient_id,
            episode_id=episode.episode_id,
            contact_id=contact_1.contact_id,
            measure_type=MeasureType.PHQ9,
            score_value=12,
            score_date=date(2026, 3, 20),
        )
    )
    service.recompute_baseline(episode.episode_id, MeasureType.PHQ9)
    contact_2 = make_contact(
        db_session, patient_id=patient.patient_id, episode_id=episode.episode_id,
        contact_date=date(2026, 3, 5),
    )
    scores.create(
        SymptomScore(
            patient_id=patient.patient_id,
            episode_id=episode.episode_id,
            contact_id=contact_2.contact_id,
            measure_type=MeasureType.PHQ9,
            score_value=20,
            score_date=date(2026, 3, 5),
        )
    )
    service.recompute_baseline(episode.episode_id, MeasureType.PHQ9)

    refreshed = service.episodes.get_by_id(episode.episode_id)
    assert refreshed.baseline_score == 20
    assert refreshed.baseline_date == date(2026, 3, 5)
