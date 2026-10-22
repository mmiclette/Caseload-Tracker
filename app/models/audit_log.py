"""
Audit log.

Satisfies CLAUDE.md's PHI requirement: "Every write to patient status, a
flag, or a score gets an audit log entry recording who made the change,
what changed, and when."

  who   — actor_provider_id, plus actor_label as a denormalized snapshot of
          the provider's name at the time. The label matters: a provider row
          can be renamed or (in a future admin flow) removed, and an audit
          trail that silently changes what it says about the past is not an
          audit trail. The FK gives you joins; the label gives you history.
          Both are nullable, because a legitimate write can have no
          authenticated provider behind it — scripts/create_admin_provider.py
          and the seed scripts talk to the repository layer directly.
  what  — action, entity_type/entity_id, and field with old_value/new_value.
  when  — occurred_at, timezone-aware UTC like every other timestamp here.

old_value and new_value are plain strings because the fields they describe
span booleans, integers, dates and enums; one readable text form keeps the
table portable (no JSONB, per the portability rule) and keeps the trail
legible to a human reviewer, which is the whole point.

patient_id is denormalized onto every row so one patient's full history is
a single indexed query, rather than a union over every entity type that
might reference them.

This table is append-only. There is no update or delete path, by design —
the same discipline as ProfileEntry, and for a stronger reason.
"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AuditAction
from app.models.mixins import utcnow


class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_log_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )

    # --- when ---
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    # --- who ---
    actor_provider_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("provider.provider_id"), nullable=True, index=True
    )
    actor_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- what ---
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", native_enum=False, length=32),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    field: Mapped[str | None] = mapped_column(String(64), nullable=True)
    old_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Why the change happened, when that isn't obvious from the fields —
    # e.g. "cascade from relapse prevention plan contact 42".
    context: Mapped[str | None] = mapped_column(String(512), nullable=True)

    actor: Mapped["Provider | None"] = relationship()  # noqa: F821
    patient: Mapped["Patient"] = relationship(back_populates="audit_entries")  # noqa: F821
