"""
Reminder model.

The BHCM landing page on login is a list of these — see CLAUDE.md's
Reporting Requirements. ReminderService.recompute_appointment_reminder is
the single place cadence math happens (mirroring the "single source of
truth" discipline used for baseline recompute and clinical thresholds
elsewhere): called after episode creation, after every recorded Contact,
and after an episode closes, it upserts one pending appointment Reminder
per patient rather than leaving a growing pile of stale ones.

referral_followup Reminders are created via ReferralService.record_referral
(see app/models/referral.py) — that call creates the Referral row and then
calls ReminderService.create_referral_reminder, which sets referral_id
below so the Reminder points back to the Referral it belongs to.
"""

from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ReminderStatus, ReminderType
from app.models.mixins import TimestampMixin


class Reminder(TimestampMixin, Base):
    __tablename__ = "reminder"

    reminder_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    episode_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("episode_of_care.episode_id"), nullable=True, index=True
    )
    referral_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("referral.referral_id"), nullable=True, index=True
    )

    reminder_type: Mapped[ReminderType] = mapped_column(
        Enum(ReminderType, name="reminder_type", native_enum=False, length=32),
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus, name="reminder_status", native_enum=False, length=16),
        nullable=False,
        default=ReminderStatus.PENDING,
    )
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="reminders")  # noqa: F821
    episode: Mapped["EpisodeOfCare | None"] = relationship(back_populates="reminders")  # noqa: F821
    referral: Mapped["Referral | None"] = relationship(back_populates="reminders")  # noqa: F821
