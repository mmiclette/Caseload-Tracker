from datetime import date

from app.models.enums import ContactType, MeasureType, ReminderStatus, ReminderType
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService
from app.services.reminder_service import ReminderService


def make_patient(db_session, mrn="MRN-REM-1", enrollment_date=date(2026, 1, 1)):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Reminder Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=enrollment_date,
            enrollment_date=enrollment_date,
        )
    )


def test_no_status_yet_means_no_reminder(db_session):
    patient = make_patient(db_session)
    service = ReminderService(db_session)

    result = service.recompute_appointment_reminder(patient.patient_id)

    assert result is None


def test_enrollment_reminder_due_seven_days_after_enrollment(db_session):
    patient = make_patient(db_session, mrn="MRN-REM-2", enrollment_date=date(2026, 1, 1))
    episode_service = EpisodeService(db_session)

    episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 5))

    reminder_repo = ReminderService(db_session).reminders
    reminder = reminder_repo.get_pending_appointment_reminder(patient.patient_id)
    assert reminder is not None
    assert reminder.due_date == date(2026, 1, 8)
    assert reminder.reminder_type == ReminderType.APPOINTMENT
    assert reminder.status == ReminderStatus.PENDING


def test_completed_contact_resets_cadence_to_fourteen_days_in_active_treatment(db_session):
    patient = make_patient(db_session, mrn="MRN-REM-3", enrollment_date=date(2026, 1, 1))
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 5)
    )
    contact_service = ContactService(db_session)

    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.INITIAL_ASSESSMENT,
        contact_date=date(2026, 1, 10),
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 18}],
    )

    reminder = ReminderService(db_session).reminders.get_pending_appointment_reminder(
        patient.patient_id
    )
    assert reminder.due_date == date(2026, 1, 24)  # 2026-01-10 + 14 days


def test_contact_attempt_does_not_reset_cadence(db_session):
    """
    A failed outreach attempt isn't a real contact — the cadence clock
    should stay anchored to the last completed contact (or enrollment, if
    none yet), not reset off the attempt.
    """
    patient = make_patient(db_session, mrn="MRN-REM-4", enrollment_date=date(2026, 1, 1))
    episode_service = EpisodeService(db_session)
    episode_service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 5))
    contact_service = ContactService(db_session)

    contact_service.record_contact(
        patient_id=patient.patient_id,
        contact_type=ContactType.CONTACT_ATTEMPT,
        contact_date=date(2026, 1, 20),
    )

    reminder = ReminderService(db_session).reminders.get_pending_appointment_reminder(
        patient.patient_id
    )
    # Still anchored to enrollment_date + 7, not the attempt date.
    assert reminder.due_date == date(2026, 1, 8)


def test_rpp_status_uses_twenty_eight_day_cadence(db_session):
    patient = make_patient(db_session, mrn="MRN-REM-5", enrollment_date=date(2026, 1, 1))
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 5)
    )
    contact_service = ContactService(db_session)

    contact_service.record_contact(
        patient_id=patient.patient_id,
        episode_id=episode.episode_id,
        contact_type=ContactType.RELAPSE_PREVENTION_PLAN,
        contact_date=date(2026, 2, 1),
        scores=[{"measure_type": MeasureType.PHQ9, "score_value": 3}],
    )

    reminder = ReminderService(db_session).reminders.get_pending_appointment_reminder(
        patient.patient_id
    )
    assert reminder.due_date == date(2026, 3, 1)  # 2026-02-01 + 28 days


def test_deactivating_episode_dismisses_pending_reminder(db_session):
    patient = make_patient(db_session, mrn="MRN-REM-6", enrollment_date=date(2026, 1, 1))
    episode_service = EpisodeService(db_session)
    episode = episode_service.create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 5)
    )

    reminder_service = ReminderService(db_session)
    pending_before = reminder_service.reminders.get_pending_appointment_reminder(patient.patient_id)
    assert pending_before is not None

    episode_service.update_episode(episode.episode_id, end_date=date(2026, 4, 1))

    pending_after = reminder_service.reminders.get_pending_appointment_reminder(patient.patient_id)
    assert pending_after is None
    history = reminder_service.reminders.list_by_patient(patient.patient_id)
    assert history[0].status == ReminderStatus.DISMISSED


def test_referral_reminder_due_four_weeks_after_referral_date(db_session):
    patient = make_patient(db_session, mrn="MRN-REM-7")
    service = ReminderService(db_session)

    reminder = service.create_referral_reminder(
        patient_id=patient.patient_id, referral_date=date(2026, 1, 1)
    )

    assert reminder.reminder_type == ReminderType.REFERRAL_FOLLOWUP
    assert reminder.due_date == date(2026, 1, 29)
    assert reminder.status == ReminderStatus.PENDING


def test_mark_completed_and_dismissed(db_session):
    patient = make_patient(db_session, mrn="MRN-REM-8")
    service = ReminderService(db_session)
    reminder = service.create_referral_reminder(
        patient_id=patient.patient_id, referral_date=date(2026, 1, 1)
    )

    completed = service.mark_completed(reminder.reminder_id)
    assert completed.status == ReminderStatus.COMPLETED

    reminder_2 = service.create_referral_reminder(
        patient_id=patient.patient_id, referral_date=date(2026, 2, 1)
    )
    dismissed = service.mark_dismissed(reminder_2.reminder_id)
    assert dismissed.status == ReminderStatus.DISMISSED
