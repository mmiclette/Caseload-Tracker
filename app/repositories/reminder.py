from sqlalchemy import select

from app.models.enums import ReminderStatus, ReminderType
from app.models.reminder import Reminder
from app.repositories.base import BaseRepository


class ReminderRepository(BaseRepository[Reminder]):
    model = Reminder

    def list_by_patient(self, patient_id: int) -> list[Reminder]:
        stmt = (
            select(Reminder)
            .where(Reminder.patient_id == patient_id)
            .order_by(Reminder.due_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_pending(self, *, limit: int = 100, offset: int = 0) -> list[Reminder]:
        """The BHCM landing-page report: every patient currently due for outreach."""
        stmt = (
            select(Reminder)
            .where(Reminder.status == ReminderStatus.PENDING)
            .order_by(Reminder.due_date)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_pending_appointment_reminder(self, patient_id: int) -> Reminder | None:
        """
        The single "current" appointment reminder ReminderService upserts
        against — a patient should have at most one pending appointment
        reminder at a time (see ReminderService.recompute_appointment_reminder).
        """
        stmt = select(Reminder).where(
            Reminder.patient_id == patient_id,
            Reminder.reminder_type == ReminderType.APPOINTMENT,
            Reminder.status == ReminderStatus.PENDING,
        )
        return self.db.execute(stmt).scalars().first()
