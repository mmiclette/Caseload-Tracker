"""
Treatment Status model.

Modeled as an append-only transition log rather than a single mutable
column on Patient. Each row is one status transition with the date it took
effect. This is intentional: episode-length and time-in-status reporting
(Phase 3) need the full history, and a single overwritten status column
would destroy that history on every update. "Current status" is derived by
reading the most recent row for a patient (see
app/services/treatment_status.py) rather than stored redundantly.

episode_id is nullable because a status transition (e.g. deactivation) can
happen without necessarily being tied to a single open episode row at the
exact moment of transition, but in normal operation it will almost always
be set.
"""

from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TreatmentStatusEnum
from app.models.mixins import TimestampMixin


class TreatmentStatus(TimestampMixin, Base):
    __tablename__ = "treatment_status"

    treatment_status_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    episode_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("episode_of_care.episode_id"), nullable=True, index=True
    )

    status: Mapped[TreatmentStatusEnum] = mapped_column(
        Enum(TreatmentStatusEnum, name="treatment_status_enum", native_enum=False, length=32),
        nullable=False,
    )
    status_changed_date: Mapped[date] = mapped_column(Date, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="treatment_statuses")  # noqa: F821
    episode: Mapped["EpisodeOfCare | None"] = relationship(  # noqa: F821
        back_populates="treatment_statuses"
    )
