"""
Reminder service.

Single source of truth for reminder-cadence thresholds (CLAUDE.md: "Don't
hardcode the remission, response, or reminder-cadence thresholds in more
than one place") — the four constants below are the only place these
numbers exist in the codebase.

recompute_appointment_reminder is called by EpisodeService (on episode
creation and on closing an episode) and by ContactService (after recording
a Contact) — see the calls there — rather than left for a caller to
remember to trigger. It upserts a single "current" pending appointment
Reminder per patient instead of leaving a growing pile of stale ones: each
call either creates the one reminder that doesn't exist yet, moves its
due_date forward to reflect a new contact resetting the cadence clock, or
dismisses it if the patient's Treatment Status is now deactivated (or has
no status at all).
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.enums import ReminderStatus, ReminderType, TreatmentStatusEnum
from app.models.reminder import Reminder
from app.repositories.contact import ContactRepository
from app.repositories.patient import PatientRepository
from app.repositories.reminder import ReminderRepository
from app.repositories.treatment_status import TreatmentStatusRepository

# The initial-assessment-scheduling reminder, per CLAUDE.md: "a reminder
# fires within 7 days of enrollment for a new episode."
ENROLLMENT_REMINDER_DAYS = 7
# Ongoing follow-up cadence once at least one Contact has happened, per
# CLAUDE.md: "every 2 weeks during active_treatment, and every 4 weeks
# during relapse_prevention_plan."
ACTIVE_TREATMENT_CADENCE_DAYS = 14
RELAPSE_PREVENTION_CADENCE_DAYS = 28
# Per CLAUDE.md: "Referral reminders fire 4 weeks after an external
# referral." Called from ReferralService.record_referral after it creates
# the Referral row (see app/models/referral.py) — this method itself stays
# usable standalone too, for a caller that already has a referral_id.
REFERRAL_FOLLOWUP_DAYS = 28


class ReminderService:
    def __init__(self, db: Session):
        self.db = db
        self.reminders = ReminderRepository(db)
        self.patients = PatientRepository(db)
        self.contacts = ContactRepository(db)
        self.statuses = TreatmentStatusRepository(db)

    def recompute_appointment_reminder(self, patient_id: int) -> Reminder | None:
        """
        Returns the patient's current pending appointment Reminder (created
        or updated as needed), or None if no appointment reminder is
        currently due (no Treatment Status yet, or deactivated).
        """
        patient = self.patients.get_by_id(patient_id)
        if patient is None:
            raise ValueError(f"Patient {patient_id} not found")

        current_status = self.statuses.get_current(patient_id)
        existing = self.reminders.get_pending_appointment_reminder(patient_id)

        if current_status is None or current_status.status == TreatmentStatusEnum.DEACTIVATED:
            if existing is not None:
                self.reminders.update(existing, status=ReminderStatus.DISMISSED)
            return None

        # A contact_attempt is outreach that didn't succeed — it shouldn't
        # reset the cadence clock, only a contact that actually happened
        # should (see ContactRepository.most_recent_completed_for_patient).
        most_recent_contact = self.contacts.most_recent_completed_for_patient(patient_id)
        if most_recent_contact is None:
            due_date = patient.enrollment_date + timedelta(days=ENROLLMENT_REMINDER_DAYS)
        else:
            cadence_days = (
                ACTIVE_TREATMENT_CADENCE_DAYS
                if current_status.status == TreatmentStatusEnum.ACTIVE_TREATMENT
                else RELAPSE_PREVENTION_CADENCE_DAYS
            )
            due_date = most_recent_contact.contact_date + timedelta(days=cadence_days)

        if existing is not None:
            if existing.due_date != due_date:
                existing = self.reminders.update(existing, due_date=due_date)
            return existing

        return self.reminders.create(
            Reminder(
                patient_id=patient_id,
                episode_id=None,
                reminder_type=ReminderType.APPOINTMENT,
                due_date=due_date,
                status=ReminderStatus.PENDING,
            )
        )

    def create_referral_reminder(
        self,
        *,
        patient_id: int,
        referral_date: date,
        referral_id: int | None = None,
        episode_id: int | None = None,
        notes: str | None = None,
    ) -> Reminder:
        due_date = referral_date + timedelta(days=REFERRAL_FOLLOWUP_DAYS)
        return self.reminders.create(
            Reminder(
                patient_id=patient_id,
                episode_id=episode_id,
                referral_id=referral_id,
                reminder_type=ReminderType.REFERRAL_FOLLOWUP,
                due_date=due_date,
                status=ReminderStatus.PENDING,
                notes=notes,
            )
        )

    def mark_completed(self, reminder_id: int) -> Reminder:
        reminder = self.reminders.get_by_id(reminder_id)
        if reminder is None:
            raise ValueError(f"Reminder {reminder_id} not found")
        return self.reminders.update(reminder, status=ReminderStatus.COMPLETED)

    def mark_dismissed(self, reminder_id: int) -> Reminder:
        reminder = self.reminders.get_by_id(reminder_id)
        if reminder is None:
            raise ValueError(f"Reminder {reminder_id} not found")
        return self.reminders.update(reminder, status=ReminderStatus.DISMISSED)
