from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CareTeamRole


class CareTeamAssignmentCreate(BaseModel):
    patient_id: int
    provider_id: int
    role: CareTeamRole
    service_begin_date: date
    service_end_date: date | None = None


class CareTeamAssignmentUpdate(BaseModel):
    service_end_date: date | None = None


class CareTeamAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    care_team_assignment_id: int
    patient_id: int
    provider_id: int
    role: CareTeamRole
    service_begin_date: date
    service_end_date: date | None
    created_at: datetime
    updated_at: datetime
