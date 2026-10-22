"""
Contact model.

Represents one recorded visit or outreach attempt. Symptom Scores collected
during a visit reference this row by contact_id (see symptom_score.py) —
Phase 1 stored contact_type directly on SymptomScore as an interim bridge
before this table existed; that field has since moved here in full,
including CONTACT_ATTEMPT, which SymptomScore's version deliberately
excluded since attempts never produce a score.

attempt_number is only meaningful for CONTACT_ATTEMPT rows — it's computed
and persisted at write time by ContactRepository.next_attempt_number,
mirroring the CTMS's "attempt #1", "attempt #2" display on the Reminders
page. It resets to 1 after any non-attempt contact.
"""

from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ContactLocation, ContactType, MedicationConfirmation
from app.models.mixins import TimestampMixin


class Contact(TimestampMixin, Base):
    __tablename__ = "contact"

    contact_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    episode_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("episode_of_care.episode_id"), nullable=True, index=True
    )
    provider_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("provider.provider_id"), nullable=True, index=True
    )

    contact_type: Mapped[ContactType] = mapped_column(
        Enum(ContactType, name="contact_type", native_enum=False, length=32),
        nullable=False,
    )
    contact_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[ContactLocation | None] = mapped_column(
        Enum(ContactLocation, name="contact_location", native_enum=False, length=16),
        nullable=True,
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Checking this is the literal mechanism that lights Patient's yellow
    # needs_psychiatric_review flag — see ContactService.record_contact.
    discuss_with_psychiatric_consultant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notes_for_consultant: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The encounter note itself (Phase 8) — what happened during the visit,
    # distinct from notes_for_consultant (the message to the Psychiatric
    # Consultant that travels with the yellow flag).
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Relapse Prevention Plan content (Phase 10) ---------------------
    # The CTMS's RPP form is a full plan document, not just a date + scores
    # (docs/ctms-reference/README.md, Matt-supplied screenshots): four
    # free-text plan fields plus a tri-state confirmation of the patient's
    # current medication list. These live on Contact rather than a separate
    # RelapsePreventionPlan entity because the CTMS records the plan AS a
    # contact — same date, same session footer, same save action — and an
    # episode can have more than one RPP contact over time, each carrying
    # that session's version of the plan. Only meaningful on
    # relapse_prevention_plan rows; ContactService rejects them elsewhere.
    other_treatments: Mapped[str | None] = mapped_column(Text, nullable=True)
    personal_warning_signs: Mapped[str | None] = mapped_column(Text, nullable=True)
    stress_reduction_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    additional_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    medications_confirmation: Mapped[MedicationConfirmation | None] = mapped_column(
        Enum(
            MedicationConfirmation,
            name="medication_confirmation",
            native_enum=False,
            length=32,
        ),
        nullable=True,
    )

    attempt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="contacts")  # noqa: F821
    episode: Mapped["EpisodeOfCare | None"] = relationship(back_populates="contacts")  # noqa: F821
    provider: Mapped["Provider | None"] = relationship(back_populates="contacts")  # noqa: F821
    scores: Mapped[list["SymptomScore"]] = relationship(  # noqa: F821
        back_populates="contact", cascade="all, delete-orphan"
    )
