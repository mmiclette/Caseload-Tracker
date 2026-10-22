from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MedicationCreate(BaseModel):
    patient_id: int
    # Either pick from the catalog (medication_key; name/dose come from the
    # picker) or record free text (medication_name alone) — see
    # MedicationService.record_medication for the resolution rules.
    medication_key: str | None = None
    medication_name: str | None = None
    dose: str | None = None
    frequency: str | None = None
    is_current: bool = True
    stop_reason: str | None = None
    recorded_by: str | None = None


class MedicationUpdate(BaseModel):
    dose: str | None = None
    frequency: str | None = None
    is_current: bool | None = None
    stop_reason: str | None = None


class MedicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    medication_id: int
    patient_id: int
    medication_key: str | None
    medication_name: str
    dose: str | None
    frequency: str | None
    is_current: bool
    stop_reason: str | None
    recorded_by: str | None
    created_at: datetime
    updated_at: datetime


class CatalogEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    display: str
    med_class: str
    doses: list[str]
