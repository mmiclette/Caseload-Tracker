"""
Episode of Care model.

An episode's baseline_score/baseline_date/baseline_measure_type are set
once, from the first validated SymptomScore recorded in the episode (see
app/services/scoring.py — this is intentionally not duplicated logic; the
service function is the single place that decides what counts as a
baseline). end_reason is only meaningful once end_date is set.
"""

from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Identity, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ConditionType, EndReason, MeasureType
from app.models.mixins import TimestampMixin


class EpisodeOfCare(TimestampMixin, Base):
    __tablename__ = "episode_of_care"

    episode_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    # The condition(s) this episode is treating. The primary diagnosis pins
    # which measure the patient's caseload response/remission metrics track
    # (CONDITION_MEASURES in app/services/scoring.py); the secondary gets a
    # dashboard trend graph but stays out of the headline rates. Both are
    # nullable — episodes recorded before these columns existed fall back
    # to what baseline_measure_type implies (MEASURE_TO_CONDITION), and
    # they're deliberately two columns rather than a diagnosis join table:
    # "primary and secondary" is exactly two slots, which is what keeps
    # the caseload metric unambiguous.
    primary_diagnosis: Mapped[ConditionType | None] = mapped_column(
        Enum(ConditionType, name="condition_type", native_enum=False, length=32),
        nullable=True,
    )
    secondary_diagnosis: Mapped[ConditionType | None] = mapped_column(
        Enum(ConditionType, name="condition_type", native_enum=False, length=32),
        nullable=True,
    )

    baseline_measure_type: Mapped[MeasureType | None] = mapped_column(
        Enum(MeasureType, name="measure_type", native_enum=False, length=16),
        nullable=True,
    )
    baseline_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    baseline_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_reason: Mapped[EndReason | None] = mapped_column(
        Enum(EndReason, name="end_reason", native_enum=False, length=32),
        nullable=True,
    )

    patient: Mapped["Patient"] = relationship(back_populates="episodes")  # noqa: F821
    symptom_scores: Mapped[list["SymptomScore"]] = relationship(  # noqa: F821
        back_populates="episode", cascade="all, delete-orphan"
    )
    treatment_statuses: Mapped[list["TreatmentStatus"]] = relationship(  # noqa: F821
        back_populates="episode", cascade="all, delete-orphan"
    )
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        back_populates="episode", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(  # noqa: F821
        back_populates="episode", cascade="all, delete-orphan"
    )
