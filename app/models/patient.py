"""
Patient model.

Per AIMS Center guidance, a patient enters the registry after consenting to
treatment and is removed after completing an episode of care. We store both
consent_date and enrollment_date as explicit dates (rather than inferring
"active" from the absence of an end date), and add deactivation_date for the
same reason: a patient's registry membership window should always be
readable directly off the row, not inferred from related tables.

program_eligibility is stored as generic JSON (not JSONB, which is
Postgres-only) since the set of eligibility flags/values varies by payer
and clinic and isn't stable enough to normalize into columns yet.

date_of_birth and race_ethnicity, and the three flag fields, were added
after confirming their exact shape against the AIMS Caseload Tracker (CTMS)
walkthrough — see CLAUDE.md's Data Model and CTMS Walkthrough Reference
sections. race_ethnicity is optional and org-configurable, so it's a JSON
list rather than a fixed set of boolean columns.

Phase 1 had a single clinic_id column here. Phase 2 replaced it with
ClinicAssignment (see that model), since the CTMS lets a patient belong to
more than one clinic over time with a primary flag and service dates — a
single string column couldn't represent that.
"""

from datetime import date

from sqlalchemy import Boolean, Date, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin
from app.types import PortableJSON


class Patient(TimestampMixin, Base):
    __tablename__ = "patient"

    patient_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    mrn: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payer: Mapped[str] = mapped_column(String(128), nullable=False)

    # Flexible bag of program-eligibility fields (varies by payer/clinic).
    # See CLAUDE.md "What's ambiguous" note before normalizing further.
    program_eligibility: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)

    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)

    # Optional, org-configurable multi-select. Values are free-form strings
    # rather than an Enum column since the CTMS lets each organization turn
    # this question on or off entirely, and the option list (American
    # Indian or Alaska Native, Asian, Black or African American, Hispanic
    # or Latino, Middle Eastern or North African, Native Hawaiian or
    # Pacific Islander, White, Patient declined) belongs in the API layer,
    # not baked into the schema.
    race_ethnicity: Mapped[list[str] | None] = mapped_column(PortableJSON, nullable=True)

    consent_date: Mapped[date] = mapped_column(Date, nullable=False)
    enrollment_date: Mapped[date] = mapped_column(Date, nullable=False)
    deactivation_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Flags (see CLAUDE.md): yellow = needs_psychiatric_review, red =
    # safety_risk, blue = custom_flag_active with an org-configurable label.
    # These are Patient-level, not Episode-level — the caseload list shows
    # one Flags column per patient regardless of how many episodes they've
    # had.
    needs_psychiatric_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    safety_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    custom_flag_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    custom_flag_label: Mapped[str | None] = mapped_column(String(128), nullable=True)

    episodes: Mapped[list["EpisodeOfCare"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    treatment_statuses: Mapped[list["TreatmentStatus"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    symptom_scores: Mapped[list["SymptomScore"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    contacts: Mapped[list["Contact"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    care_team_assignments: Mapped[list["CareTeamAssignment"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    clinic_assignments: Mapped[list["ClinicAssignment"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    consultations: Mapped[list["Consultation"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    referrals: Mapped[list["Referral"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    medications: Mapped[list["Medication"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    profile_entries: Mapped[list["ProfileEntry"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )
    audit_entries: Mapped[list["AuditLog"]] = relationship(  # noqa: F821
        back_populates="patient", cascade="all, delete-orphan"
    )

    @property
    def age(self) -> int:
        """
        Computed from date_of_birth, never stored — the CTMS caseload list
        displays Age as a column, but it's derived, not persisted, so it's
        never stale.
        """
        today = date.today()
        years = today.year - self.date_of_birth.year
        had_birthday_this_year = (today.month, today.day) >= (
            self.date_of_birth.month,
            self.date_of_birth.day,
        )
        if not had_birthday_this_year:
            years -= 1
        return years
