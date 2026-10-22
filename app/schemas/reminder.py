from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ReminderStatus, ReminderType


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reminder_id: int
    patient_id: int
    episode_id: int | None
    referral_id: int | None
    reminder_type: ReminderType
    due_date: date
    status: ReminderStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ReminderStatusUpdate(BaseModel):
    status: ReminderStatus
