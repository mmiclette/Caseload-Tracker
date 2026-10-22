from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PatientBase(BaseModel):
    mrn: str
    name: str
    payer: str
    program_eligibility: dict | None = None
    date_of_birth: date
    # Optional, org-configurable multi-select. Expected values (org can
    # choose to ask this at all — see CLAUDE.md): "american_indian_or_alaska_native",
    # "asian", "black_or_african_american", "hispanic_or_latino",
    # "middle_eastern_or_north_african", "native_hawaiian_or_pacific_islander",
    # "white", "patient_declined".
    race_ethnicity: list[str] | None = None
    consent_date: date
    enrollment_date: date
    deactivation_date: date | None = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    name: str | None = None
    payer: str | None = None
    program_eligibility: dict | None = None
    race_ethnicity: list[str] | None = None
    deactivation_date: date | None = None
    needs_psychiatric_review: bool | None = None
    safety_risk: bool | None = None
    custom_flag_active: bool | None = None
    custom_flag_label: str | None = None


class PatientRead(PatientBase):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int
    needs_psychiatric_review: bool
    safety_risk: bool
    custom_flag_active: bool
    custom_flag_label: str | None
    age: int
    created_at: datetime
    updated_at: datetime
