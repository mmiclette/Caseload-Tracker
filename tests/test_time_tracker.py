from datetime import date

from app.models.enums import ContactType, EndReason
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService
from app.services.time_tracker import WINDOW_MONTHS, build_monthly_time_tracker


def make_patient(db_session, mrn):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Time Tracker Test Patient",
            payer="Medicaid",
            date_of_birth=date(1991, 2, 14),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def test_no_billable_contacts_means_no_rows(db_session):
    rows = build_monthly_time_tracker(db_session, date(2026, 6, 15))
    assert rows == []


def test_thirteen_months_returned_oldest_to_newest(db_session):
    patient = make_patient(db_session, "MRN-TT-1")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 6, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 6, 5),
        duration_minutes=45,
    )

    rows = build_monthly_time_tracker(db_session, date(2026, 6, 15))
    assert len(rows) == 1
    row = rows[0]
    assert len(row.months) == WINDOW_MONTHS
    assert (row.months[0].year, row.months[0].month) == (2025, 6)
    assert (row.months[-1].year, row.months[-1].month) == (2026, 6)


def test_minutes_summed_per_month_and_excludes_contact_attempts(db_session):
    patient = make_patient(db_session, "MRN-TT-2")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 6, 1))

    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 6, 5),
        duration_minutes=45,
    )
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.FOLLOW_UP,
        contact_date=date(2026, 6, 20),
        duration_minutes=30,
    )
    # A contact_attempt has no duration and shouldn't count even if it did.
    contact_service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 6, 25),
    )

    rows = build_monthly_time_tracker(db_session, date(2026, 6, 15))
    row = rows[0]
    june = next(m for m in row.months if (m.year, m.month) == (2026, 6))
    assert june.minutes == 75
    assert row.total_minutes == 75


def test_deactivated_patient_still_appears_for_minutes_billed_in_window(db_session):
    patient = make_patient(db_session, "MRN-TT-3")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 5),
        duration_minutes=50,
    )
    episode_service.update_episode(episode.episode_id, end_date=date(2026, 2, 1), end_reason=EndReason.ACHIEVED_GOALS)

    rows = build_monthly_time_tracker(db_session, date(2026, 6, 15))
    assert len(rows) == 1
    row = rows[0]
    january = next(m for m in row.months if (m.year, m.month) == (2026, 1))
    assert january.minutes == 50
    assert row.total_minutes == 50


def test_contact_outside_window_not_counted(db_session):
    patient = make_patient(db_session, "MRN-TT-4")
    episode_service = EpisodeService(db_session)
    contact_service = ContactService(db_session)
    episode = episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2024, 1, 1))
    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2024, 1, 5),
        duration_minutes=50,
    )

    rows = build_monthly_time_tracker(db_session, date(2026, 6, 15))
    assert rows == []
