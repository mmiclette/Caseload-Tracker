from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ClinicAssignmentCreate(BaseModel):
    patient_id: int
    clinic_id: str
    is_primary: bool = False
    service_begin_date: date
    service_end_date: date | None = None


class ClinicAssignmentUpdate(BaseModel):
    is_primary: bool | None = None
    service_end_date: date | None = None


class ClinicAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_assignment_id: int
    patient_id: int
    clinic_id: str
    is_primary: bool
    service_begin_date: date
    service_end_date: date | None
    created_at: datetime
    updated_at: datetime
