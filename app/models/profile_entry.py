"""
Profile Entry model.

The generic entity behind the patient profile's free-form sections
(ProfileSection — Behavioral Health, Medical Profile, Safety & Risk,
Substance Use, Social & Environmental, plus allergies/intolerances under
Current Medications). The interaction model is click-a-sub-field,
add-a-value: each entry is stamped with a clinical date and optional
context, and the table is APPEND-ONLY — a changed circumstance is a new
entry that supersedes the old one at display time (latest per sub-field),
never an update or delete. That keeps the full history readable and gives
the PHI audit trail for free. There are deliberately no update/delete
routes; even a typo is corrected by a superseding entry.

sub_field is a plain string, not an enum — the per-section sub-field lists
(diagnoses, living_situation, access_to_firearms, ...) are org-configurable
suggestions served by GET /profile-entries/sections (see
app/services/profile_entry_service.py), the same "option list belongs in
the API layer, not baked into the schema" treatment as
Patient.race_ethnicity.

Safety & Risk entries document risk factors (previous attempts, firearms
access, safety plan), but Patient.safety_risk — the red flag — remains the
single alerting signal on the caseload list. An entry here never sets or
clears that flag, and nothing should derive a second "is this patient at
risk" boolean from these rows.
"""

from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ProfileSection
from app.models.mixins import TimestampMixin


class ProfileEntry(TimestampMixin, Base):
    __tablename__ = "profile_entry"

    profile_entry_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    section: Mapped[ProfileSection] = mapped_column(
        Enum(ProfileSection, name="profile_section", native_enum=False, length=32),
        nullable=False,
    )
    sub_field: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String(2048), nullable=False)
    context: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="profile_entries")  # noqa: F821
