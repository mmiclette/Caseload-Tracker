"""
Profile Entry service.

Single entry point for adding patient-profile entries (see
app/models/profile_entry.py for the append-only design). There is
intentionally no update or delete: a changed circumstance — or a typo —
is a new entry that supersedes the old one at display time.

SECTION_SUB_FIELD_SUGGESTIONS is the default click-to-add picker content
per section, transcribed from the confirmed patient-profile design table
(2026-08). They are suggestions, not validation — any non-empty sub_field
is accepted, and the lists are expected to become org-configurable
alongside the other org-level toggles once an Organization entity exists
(see CLAUDE.md's Multi-tenancy entry). Don't promote them into an enum.

CURRENT_MEDICATIONS deliberately suggests only allergies_intolerances:
the medications themselves live on the Medication entity, and this
section must never accumulate free-text medication rows next to it.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import ProfileSection
from app.models.profile_entry import ProfileEntry
from app.repositories.patient import PatientRepository
from app.repositories.profile_entry import ProfileEntryRepository

SECTION_SUB_FIELD_SUGGESTIONS: dict[ProfileSection, list[str]] = {
    # "diagnoses" and "symptom_severity" are deliberately absent: the
    # treated diagnoses are Episode.primary_diagnosis/secondary_diagnosis
    # (structured, driving reports and dashboard graphs), and severity IS
    # the symptom score — free-text twins of either would drift from the
    # source of truth.
    ProfileSection.BEHAVIORAL_HEALTH: [
        "duration",
        "current_concerns",
        "treatment_goals",
    ],
    ProfileSection.CURRENT_MEDICATIONS: [
        "allergies_intolerances",
    ],
    ProfileSection.MEDICAL_PROFILE: [
        "active_medical_conditions",
        "pregnancy_status",
        "sleep_disorders",
        "chronic_pain",
    ],
    ProfileSection.SAFETY_AND_RISK: [
        "suicide_risk",
        "violence_risk",
        "previous_attempts",
        "access_to_firearms",
        "safety_plan",
    ],
    ProfileSection.SUBSTANCE_USE: [
        "alcohol",
        "nicotine",
        "cannabis",
        "other_substances",
        "recovery_supports",
    ],
    ProfileSection.SOCIAL_ENVIRONMENTAL: [
        "living_situation",
        "employment",
        "transportation",
        "financial_barriers",
        "social_support",
        "technology_access",
    ],
}


class ProfileEntryService:
    def __init__(self, db: Session):
        self.db = db
        self.entries = ProfileEntryRepository(db)
        self.patients = PatientRepository(db)

    def record_entry(
        self,
        *,
        patient_id: int,
        section: ProfileSection,
        sub_field: str,
        value: str,
        context: str | None = None,
        recorded_date: date | None = None,
        recorded_by: str | None = None,
    ) -> ProfileEntry:
        if self.patients.get_by_id(patient_id) is None:
            raise ValueError(f"Patient {patient_id} not found")

        sub_field = sub_field.strip()
        if not sub_field:
            raise ValueError("sub_field must not be empty")
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")

        return self.entries.create(
            ProfileEntry(
                patient_id=patient_id,
                section=section,
                sub_field=sub_field,
                value=value,
                context=context,
                recorded_date=recorded_date or date.today(),
                recorded_by=recorded_by,
            )
        )
