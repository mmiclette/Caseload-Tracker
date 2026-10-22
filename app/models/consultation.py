"""
Consultation model.

Recording a Consultation is what clears Patient.needs_psychiatric_review
(the yellow flag) — see ConsultationService.record_consultation. If this
consultation itself flags the patient for a future review
(flagged_for_next_review=True), the flag is immediately re-set rather than
left clear, since that's a distinct concept from the flag this consultation
is clearing: "we reviewed this today" vs. "review this again next time."
"""

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class Consultation(TimestampMixin, Base):
    __tablename__ = "consultation"

    consultation_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    provider_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("provider.provider_id"), nullable=True, index=True
    )

    consultation_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Phase 9: the CTMS's Minutes This Month tooltip confirms psychiatric
    # consultations count toward a patient's minutes of service (CoCM
    # billing counts consultant time), so a consultation carries its own
    # duration like a Contact does.
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendations_forwarded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    flagged_for_next_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    flag_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # The consultation note (Phase 8): the Psychiatric Consultant's
    # findings and recommendations from the review —
    # recommendations_forwarded above tracks whether they reached the PCP.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="consultations")  # noqa: F821
    provider: Mapped["Provider | None"] = relationship(back_populates="consultations")  # noqa: F821
