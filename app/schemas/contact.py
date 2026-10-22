from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    ContactLocation,
    ContactType,
    MeasureType,
    MedicationConfirmation,
)


class ContactScoreInput(BaseModel):
    """One scale score collected during a contact. See ContactCreate.scores."""

    measure_type: MeasureType
    score_value: int
    recorded_by: str | None = None


class ContactCreate(BaseModel):
    patient_id: int
    episode_id: int | None = None
    provider_id: int | None = None
    contact_type: ContactType
    contact_date: date
    location: ContactLocation | None = None
    duration_minutes: int | None = None
    discuss_with_psychiatric_consultant: bool = False
    notes_for_consultant: str | None = None
    # The encounter note — what happened during the visit, distinct from
    # notes_for_consultant (the message that travels with the yellow flag).
    notes: str | None = None
    # Relapse Prevention Plan content — only valid when contact_type is
    # relapse_prevention_plan (ContactService enforces this).
    other_treatments: str | None = None
    personal_warning_signs: str | None = None
    stress_reduction_plan: str | None = None
    additional_comments: str | None = None
    medications_confirmation: MedicationConfirmation | None = None
    # Scores collected during this same contact, e.g. a PHQ-9 and a GAD-7
    # entered together on one visit. Empty for a contact_attempt, and
    # legitimately empty for a completed visit where no scale was done —
    # see CLAUDE.md's "proportion of contacts with a completed scale"
    # reporting metric, which only makes sense if that proportion isn't 100%.
    scores: list[ContactScoreInput] = []


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contact_id: int
    patient_id: int
    episode_id: int | None
    provider_id: int | None
    contact_type: ContactType
    contact_date: date
    location: ContactLocation | None
    duration_minutes: int | None
    discuss_with_psychiatric_consultant: bool
    notes_for_consultant: str | None
    notes: str | None
    other_treatments: str | None
    personal_warning_signs: str | None
    stress_reduction_plan: str | None
    additional_comments: str | None
    medications_confirmation: MedicationConfirmation | None
    attempt_number: int | None
    created_at: datetime
    updated_at: datetime
