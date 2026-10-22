"""
Referral service.

record_referral is the single entry point for logging an external
referral — it creates the Referral row and, in the same call, creates its
4-week follow-up Reminder pointed back at it (see ReminderService), so a
caller can't create one without the other the way the old
POST /reminders-with-a-bare-referral_date endpoint allowed.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.referral import Referral
from app.repositories.referral import ReferralRepository
from app.services.reminder_service import ReminderService


class ReferralService:
    def __init__(self, db: Session):
        self.db = db
        self.referrals = ReferralRepository(db)
        self.reminder_service = ReminderService(db)

    def record_referral(
        self,
        *,
        patient_id: int,
        referral_date: date,
        referred_by_provider_id: int | None = None,
        referred_to: str | None = None,
        reason: str | None = None,
    ) -> Referral:
        referral = self.referrals.create(
            Referral(
                patient_id=patient_id,
                referred_by_provider_id=referred_by_provider_id,
                referred_to=referred_to,
                referral_date=referral_date,
                reason=reason,
            )
        )
        self.reminder_service.create_referral_reminder(
            patient_id=patient_id,
            referral_date=referral_date,
            referral_id=referral.referral_id,
            notes=reason,
        )
        return referral
