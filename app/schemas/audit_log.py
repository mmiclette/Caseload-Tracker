from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AuditAction


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_log_id: int
    occurred_at: datetime
    actor_provider_id: int | None
    actor_label: str | None
    action: AuditAction
    entity_type: str
    entity_id: int | None
    patient_id: int
    field: str | None
    old_value: str | None
    new_value: str | None
    context: str | None
