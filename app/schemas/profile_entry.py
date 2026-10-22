from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ProfileSection


class ProfileEntryCreate(BaseModel):
    patient_id: int
    section: ProfileSection
    sub_field: str
    value: str
    context: str | None = None
    # Defaults to today in the service when omitted — the clinical "date
    # added"; created_at separately records the row's write time.
    recorded_date: date | None = None
    recorded_by: str | None = None


class ProfileEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_entry_id: int
    patient_id: int
    section: ProfileSection
    sub_field: str
    value: str
    context: str | None
    recorded_date: date
    recorded_by: str | None
    created_at: datetime
    updated_at: datetime


class ProfileSectionRead(BaseModel):
    section: ProfileSection
    # Suggestions for the click-to-add picker, not validation — any
    # sub_field string is accepted on write.
    sub_field_suggestions: list[str]
