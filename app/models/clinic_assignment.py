"""
Clinic Assignment model.

Replaces Phase 1's single Patient.clinic_id column. The CTMS lets a patient
belong to more than one clinic over time with an is_primary flag and a
service window (the Clinical Dashboard's "Current Clinics" table) — a
single string column on Patient couldn't represent that, so this is its
own table.

clinic_id stays a plain string identifier here rather than a foreign key
to a separate Clinic table, matching how Patient.clinic_id was modeled in
Phase 1 — CLAUDE.md's data model never called for a full Clinic entity
(name, address, etc.), only an identifier to group and filter by.
"""

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class ClinicAssignment(TimestampMixin, Base):
    __tablename__ = "clinic_assignment"

    clinic_assignment_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    clinic_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    service_begin_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="clinic_assignments")  # noqa: F821
