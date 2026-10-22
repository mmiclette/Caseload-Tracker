"""
Medication model.

The AIMS design-considerations guide lists "medications at that visit,
dosage" in the patient-level summary and "whether psychotropic medications
are prescribed" as a caseload column, but the CTMS walkthrough never showed
a medications screen — so this entity follows the guide beyond confirmed
CTMS parity, a deliberate product extension (same "flag it, don't present
it as confirmed" discipline as ContactLocation).

Fields are exactly the confirmed spec: medication name, dose, frequency,
whether it's current or past, and — if past — why it was stopped. No
start/end dates were asked for; is_current is the record of state, not a
derived value.

medication_key links a row to the vendored bh-cds catalog (see
app/services/medication_catalog.py) when the medication was picked from
the search-as-you-type picker. It's nullable because patients take
medications outside the behavioral-health catalog (e.g. metformin), which
are recorded as free text with no key. Because every catalog entry is a
behavioral-health medication by construction, a current row with a
non-null medication_key is what the Active Patients report counts as
"psychotropic medications prescribed" — a free-text row can't be
classified and deliberately doesn't count (documented as an assumption in
app/services/reporting.py).

dose is a string, not a number, because catalog display doses aren't
always a single mg value ("8mg/2mg" for buprenorphine/naloxone). frequency
and stop_reason are free text — no confirmed vocabulary exists for either,
and inventing an enum would violate the "flag it, don't invent it"
discipline.
"""

from sqlalchemy import Boolean, ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class Medication(TimestampMixin, Base):
    __tablename__ = "medication"

    medication_id: Mapped[int] = mapped_column(
        Integer, Identity(always=False), primary_key=True
    )
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patient.patient_id"), nullable=False, index=True
    )
    # Vendored-catalog key when picked from the med picker; null for a
    # free-text (non-catalog) medication.
    medication_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    medication_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dose: Mapped[str | None] = mapped_column(String(128), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Only meaningful when is_current is False — MedicationService rejects a
    # stop_reason on a current medication. Nullable even for past
    # medications (a historical med with an unknown stop reason is real
    # data; reports can surface "not recorded" rather than the schema
    # forcing an invented reason).
    stop_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    patient: Mapped["Patient"] = relationship(back_populates="medications")  # noqa: F821
