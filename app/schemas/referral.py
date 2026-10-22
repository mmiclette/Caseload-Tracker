from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ReferralCreate(BaseModel):
    patient_id: int
    referral_date: date
    referred_by_provider_id: int | None = None
    referred_to: str | None = None
    reason: str | None = None


class ReferralRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    referral_id: int
    patient_id: int
    referred_by_provider_id: int | None
    referred_to: str | None
    referral_date: date
    reason: str | None
    created_at: datetime
    updated_at: datetime
