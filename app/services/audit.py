"""
Audit service.

The single place audit entries are written, so the shape of the trail stays
consistent and the "who / what / when" contract lives in one file.

**Actor plumbing.** Routes bind the authenticated provider
(`Depends(get_current_provider)`) and pass it down as `actor`. FastAPI
caches that dependency per request, so binding it in a route function costs
nothing extra beyond the router-level check that was already there. `actor`
is optional because writes legitimately happen with no authenticated
provider behind them — scripts/create_admin_provider.py and the seed
scripts go through the repository layer directly, and an entry recording
"what changed and when" with an unknown actor is far better than no entry.
tests/test_audit_log.py asserts the real HTTP routes do supply one, so a
route that forgets stays caught.

**Transaction boundary — a known limitation, stated plainly.** Each entry
is committed in its own transaction, because BaseRepository.create commits
and the service layer already commits per repository call (a single
`record_contact` commits the contact, then the scores, then the status
transition). So a change and its audit entry are not atomic: a crash
between them could leave one without the other. Making them atomic means a
session-scoped unit of work across the whole service layer, which is a
worthwhile refactor but a much larger one than adding this table, and doing
it badly would be worse than this. Flagged here rather than hidden.
"""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from app.models.provider import Provider
from app.repositories.audit_log import AuditLogRepository


def _render(value: Any) -> str | None:
    """
    One readable text form for every audited value, so old_value/new_value
    stay portable strings instead of a JSON column (see the portability
    rule in CLAUDE.md). Enums render as their value, dates as ISO, None as
    None rather than the string "None" — an absent value and the text
    "None" must not be indistinguishable in an audit trail.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "value"):  # a PEP-435 enum
        return str(value.value)
    return str(value)


class AuditService:
    def __init__(self, db: Session):
        self.db = db
        self.entries = AuditLogRepository(db)

    def record(
        self,
        *,
        action: AuditAction,
        entity_type: str,
        patient_id: int,
        entity_id: int | None = None,
        actor: Provider | None = None,
        field: str | None = None,
        old_value: Any = None,
        new_value: Any = None,
        context: str | None = None,
    ) -> AuditLog:
        return self.entries.create(
            AuditLog(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                patient_id=patient_id,
                actor_provider_id=actor.provider_id if actor else None,
                actor_label=actor.name if actor else None,
                field=field,
                old_value=_render(old_value),
                new_value=_render(new_value),
                context=context,
            )
        )

    def record_flag_change(
        self,
        *,
        patient_id: int,
        field: str,
        old_value: bool,
        new_value: bool,
        actor: Provider | None = None,
        context: str | None = None,
    ) -> AuditLog:
        """A flag going up and a flag coming down are different events."""
        return self.record(
            action=AuditAction.FLAG_SET if new_value else AuditAction.FLAG_CLEARED,
            entity_type="patient",
            entity_id=patient_id,
            patient_id=patient_id,
            actor=actor,
            field=field,
            old_value=old_value,
            new_value=new_value,
            context=context,
        )
