from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ConditionType, EndReason, MeasureType, TreatmentStatusEnum


class EpisodeCreate(BaseModel):
    patient_id: int
    start_date: date
    primary_diagnosis: ConditionType | None = None
    secondary_diagnosis: ConditionType | None = None


class EpisodeUpdate(BaseModel):
    end_date: date | None = None
    end_reason: EndReason | None = None
    primary_diagnosis: ConditionType | None = None
    secondary_diagnosis: ConditionType | None = None


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    episode_id: int
    patient_id: int
    start_date: date
    primary_diagnosis: ConditionType | None
    secondary_diagnosis: ConditionType | None
    baseline_measure_type: MeasureType | None
    baseline_score: int | None
    baseline_date: date | None
    end_date: date | None
    end_reason: EndReason | None
    created_at: datetime
    updated_at: datetime


# SymptomScoreCreate is gone — scores are only ever created as part of a
# Contact now (see app/schemas/contact.py ContactCreate.scores), through
# ContactService.record_contact. There's no standalone "add a score"
# operation any more, matching the CTMS's own contact-recording form (one
# save button for the visit date, every scale score, and the psychiatric
# consultant checkbox together).


class SymptomScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score_id: int
    episode_id: int
    patient_id: int
    contact_id: int
    measure_type: MeasureType
    score_value: int
    score_date: date
    recorded_by: str | None


class TreatmentStatusTransition(BaseModel):
    status: TreatmentStatusEnum
    status_changed_date: date
    changed_by: str | None = None
    notes: str | None = None


class TreatmentStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    treatment_status_id: int
    patient_id: int
    episode_id: int | None
    status: TreatmentStatusEnum
    status_changed_date: date
    changed_by: str | None
    notes: str | None
