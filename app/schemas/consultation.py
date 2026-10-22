from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ConsultationCreate(BaseModel):
    patient_id: int
    provider_id: int | None = None
    consultation_date: date
    duration_minutes: int | None = None
    recommendations_forwarded: bool = False
    flagged_for_next_review: bool = False
    flag_reason: str | None = None
    # The consultation note: the Psychiatric Consultant's findings and
    # recommendations from the review.
    notes: str | None = None


class ConsultationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consultation_id: int
    patient_id: int
    provider_id: int | None
    consultation_date: date
    duration_minutes: int | None
    recommendations_forwarded: bool
    flagged_for_next_review: bool
    flag_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
