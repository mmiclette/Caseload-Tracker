"""
Symptom Score model.

Remission/response/improvement thresholds are NOT computed here. They live
exclusively in app/services/scoring.py so the numbers (PHQ-9 < 5 for
remission, 50% baseline improvement for response, 5-point improvement for
GAD-7) exist in exactly one place in the codebase, per CLAUDE.md.

Phase 1 stored contact_type directly on this table as an interim bridge,
before the Contact entity existed. Phase 2 replaced that with a real
contact_id foreign key — every score now belongs to a specific Contact
(see contact.py), and contact_type/contact_date/provider are read off that
row rather than duplicated here. patient_id and episode_id stay directly on
this table (denormalized from Contact) since caseload and episode reporting
query scores far more often than they need to join through Contact.
"""

from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import MeasureType
from app.models.mixins import TimestampMixin


class SymptomScore(TimestampMixin, Base):
    __tablename__ = "symptom_score"

    score_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    episode_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("episode_of_care.episode_id"), nullable=False, index=True
    )
    contact_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contact.contact_id"), nullable=False, index=True
    )

    measure_type: Mapped[MeasureType] = mapped_column(
        Enum(MeasureType, name="measure_type_score", native_enum=False, length=16),
        nullable=False,
    )
    score_value: Mapped[int] = mapped_column(Integer, nullable=False)
    score_date: Mapped[date] = mapped_column(Date, nullable=False)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="symptom_scores")  # noqa: F821
    episode: Mapped["EpisodeOfCare"] = relationship(back_populates="symptom_scores")  # noqa: F821
    contact: Mapped["Contact"] = relationship(back_populates="scores")  # noqa: F821
