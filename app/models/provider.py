"""
Provider model.

Added in Phase 2, ahead of real authentication, per the explicit decision
in CLAUDE.md: recorded_by/changed_by/provider_name fields as free text
would need a painful migration to real foreign keys later, right when
Phase 2's own reporting work (caseload filtered by provider, "cover for a
colleague's caseload") starts needing a real Provider to filter by.

Phase 3 adds hashed_password: a Provider is now also the account a person
logs in with (see app/core/security.py and app/routes/auth.py). email is
unique so it can serve as the login identifier, matching the case-
sensitive-unique-plus-case-insensitive-lookup pattern already used for
Patient.mrn (see ProviderRepository.get_by_email and
routes/providers.py's pre-insert check, mirroring routes/patients.py).
hashed_password stays nullable — a Provider created without a password
(e.g. via a seed script, or one representing a role that never logs in
directly) simply can't authenticate, rather than that being an error.
"""

from sqlalchemy import Enum, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ProviderRole
from app.models.mixins import TimestampMixin


class Provider(TimestampMixin, Base):
    __tablename__ = "provider"

    provider_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[ProviderRole] = mapped_column(
        Enum(ProviderRole, name="provider_role", native_enum=False, length=32),
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="provider")  # noqa: F821
    care_team_assignments: Mapped[list["CareTeamAssignment"]] = relationship(  # noqa: F821
        back_populates="provider"
    )
    consultations: Mapped[list["Consultation"]] = relationship(back_populates="provider")  # noqa: F821
    referrals_made: Mapped[list["Referral"]] = relationship(back_populates="referred_by")  # noqa: F821
