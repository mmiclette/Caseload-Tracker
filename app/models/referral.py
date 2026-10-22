"""
Referral model.

Closes a gap Phase 3 originally left open: referral_followup Reminders
used to be created from a bare referral_date with no record of the
referral itself. This is the real entity — who referred the patient,
where the referral went, and why — with the Reminder that tracks its
4-week follow-up now pointing back to it via Reminder.referral_id (see
ReferralService.record_referral), rather than the Reminder being the only
trace a referral ever happened.

referred_to is a plain string, not a foreign key to a directory of
external providers — this registry has no entity for organizations or
people outside its own CoCM team, and CLAUDE.md never called for one. That
mirrors the same "plain string, not a foreign key to something that
doesn't exist" choice already made for ClinicAssignment.clinic_id.
referred_by_provider_id, in contrast, IS a real foreign key — an internal
CoCM team member (e.g. the Care Manager) initiating an external referral
is exactly the kind of "who did this" that Provider exists to answer.
"""

from datetime import date

from sqlalchemy import Date, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class Referral(TimestampMixin, Base):
    __tablename__ = "referral"

    referral_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    referred_by_provider_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("provider.provider_id"), nullable=True, index=True
    )
    referred_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    referral_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="referrals")  # noqa: F821
    referred_by: Mapped["Provider | None"] = relationship(back_populates="referrals_made")  # noqa: F821
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="referral")  # noqa: F821
