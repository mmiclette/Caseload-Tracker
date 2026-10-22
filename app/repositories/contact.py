from datetime import date

from sqlalchemy import select

from app.models.contact import Contact
from app.models.enums import ContactType
from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    model = Contact

    def list_patient_ids_with_billable_contact_between(self, start: date, end: date) -> list[int]:
        """
        Distinct patients with at least one completed (non-attempt),
        timed Contact in [start, end] — used by Monthly Time Tracker to
        find which patients belong in the report at all, without scanning
        every patient in the registry.
        """
        stmt = (
            select(Contact.patient_id)
            .distinct()
            .where(
                Contact.contact_type != ContactType.CONTACT_ATTEMPT,
                Contact.duration_minutes.is_not(None),
                Contact.contact_date >= start,
                Contact.contact_date <= end,
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_patient(self, patient_id: int) -> list[Contact]:
        stmt = (
            select(Contact)
            .where(Contact.patient_id == patient_id)
            .order_by(Contact.contact_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_episode(self, episode_id: int) -> list[Contact]:
        stmt = (
            select(Contact)
            .where(Contact.episode_id == episode_id)
            .order_by(Contact.contact_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def most_recent_for_patient(self, patient_id: int) -> Contact | None:
        stmt = (
            select(Contact)
            .where(Contact.patient_id == patient_id)
            .order_by(Contact.contact_date.desc(), Contact.contact_id.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def most_recent_completed_for_patient(self, patient_id: int) -> Contact | None:
        """
        Like most_recent_for_patient, but excludes contact_attempt rows —
        a failed outreach attempt shouldn't reset the follow-up cadence
        clock (see ReminderService.recompute_appointment_reminder); only a
        contact that actually happened should. care_team_collaboration is
        excluded for the same reason: the patient wasn't present, so
        they're still due for outreach.
        """
        stmt = (
            select(Contact)
            .where(
                Contact.patient_id == patient_id,
                Contact.contact_type.not_in(
                    [ContactType.CONTACT_ATTEMPT, ContactType.CARE_TEAM_COLLABORATION]
                ),
            )
            .order_by(Contact.contact_date.desc(), Contact.contact_id.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def next_attempt_number(self, patient_id: int) -> int:
        """
        The CTMS's Reminders page shows contact attempts with a running
        counter ("attempt #1", "attempt #2") that resets once a real
        contact happens. This mirrors that: 1 if the most recent contact
        for this patient wasn't itself an attempt (or there is none yet),
        otherwise one more than that attempt's number.
        care_team_collaboration rows are skipped entirely — an about-the-
        patient activity is neither a failed attempt nor a reached patient,
        so it neither increments nor resets the counter.
        """
        stmt = (
            select(Contact)
            .where(
                Contact.patient_id == patient_id,
                Contact.contact_type != ContactType.CARE_TEAM_COLLABORATION,
            )
            .order_by(Contact.contact_date.desc(), Contact.contact_id.desc())
        )
        most_recent = self.db.execute(stmt).scalars().first()
        if most_recent is None or most_recent.contact_type != ContactType.CONTACT_ATTEMPT:
            return 1
        return (most_recent.attempt_number or 0) + 1
