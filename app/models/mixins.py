"""
Shared column mixins.

Timestamps are populated in Python (not via server-side `now()` functions)
so that identical behavior is guaranteed on both Postgres and Snowflake,
which do not share a `now()`/`CURRENT_TIMESTAMP` implementation in every
SQLAlchemy dialect path. Every timestamp is timezone-aware UTC.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
