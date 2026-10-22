from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def list_by_patient(self, patient_id: int, *, limit: int = 200) -> list[AuditLog]:
        """Newest first — a reviewer reads an audit trail backwards from now."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.patient_id == patient_id)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.audit_log_id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_recent(self, *, limit: int = 200) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.audit_log_id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    # No update() or delete() override is needed — BaseRepository provides
    # them, but nothing calls them for this table and no route exposes them.
    # An audit log that can be edited is not an audit log.
