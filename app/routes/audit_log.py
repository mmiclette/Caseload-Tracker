from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.database import get_db
from app.repositories.audit_log import AuditLogRepository
from app.schemas.audit_log import AuditLogRead

router = APIRouter(
    prefix="/audit-log", tags=["audit-log"], dependencies=[Depends(get_current_provider)]
)

# Read-only by design. There is no POST here: audit entries are written by
# AuditService as a side effect of the change they describe, never by a
# client asking for one. And there is no PATCH or DELETE, because an audit
# trail that can be edited is not an audit trail.


@router.get("", response_model=list[AuditLogRead])
def list_audit_entries(
    patient_id: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """
    Newest first. With patient_id, one patient's full trail — which is what
    the Clinical Dashboard's per-section "last updated by" lines need.
    Without it, the most recent activity across the program.
    """
    repo = AuditLogRepository(db)
    if patient_id is not None:
        return repo.list_by_patient(patient_id, limit=limit)
    return repo.list_recent(limit=limit)
