"""
Care Team Assignment model.

Links a Patient to a Provider with a role, for a span of time. The Clinical
Dashboard's "Current Providers" table (Care Manager, PCP, Psychiatric
Consultant, each with contact info and a service window) is built from
exactly this shape. A patient can have more than one provider per role over
time — e.g. a new Care Manager taking over a caseload — so this is its own
table with service_begin_date/service_end_date, not columns on Patient.

"Current" providers are the rows where service_end_date is null (or in the
future); ended assignments stay for history rather than being deleted.
"""

from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Identity, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import CareTeamRole
from app.models.mixins import TimestampMixin


class CareTeamAssignment(TimestampMixin, Base):
    __tablename__ = "care_team_assignment"

    care_team_assignment_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("provider.provider_id"), nullable=False, index=True
    )

    role: Mapped[CareTeamRole] = mapped_column(
        Enum(CareTeamRole, name="care_team_role", native_enum=False, length=32),
        nullable=False,
    )
    service_begin_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="care_team_assignments")  # noqa: F821
    provider: Mapped["Provider"] = relationship(back_populates="care_team_assignments")  # noqa: F821
