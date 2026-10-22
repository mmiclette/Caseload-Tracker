"""
Medication service.

Single entry point for recording and updating a patient's medications,
following the same server-side-validation discipline as ContactService:
the rules live here, not in the frontend.

Rules enforced:
  - A catalog-picked medication (medication_key set) must reference a real
    catalog entry; its display name always comes from the catalog so the
    stored name can't drift from the key.
  - A free-text medication (no key) must supply medication_name.
  - stop_reason is only valid on a past medication. It's not *required*
    when a medication is marked past (a historical med with an unknown
    stop reason is real data), but a current medication carrying a
    stop_reason is a contradiction and is rejected.
  - Marking a past medication current again clears its stop_reason —
    "restarted" and "stopped because X" can't both be true.
"""

from sqlalchemy.orm import Session

from app.models.medication import Medication
from app.repositories.medication import MedicationRepository
from app.repositories.patient import PatientRepository
from app.services.medication_catalog import get_catalog_entry


class MedicationService:
    def __init__(self, db: Session):
        self.db = db
        self.medications = MedicationRepository(db)
        self.patients = PatientRepository(db)

    def record_medication(
        self,
        *,
        patient_id: int,
        medication_key: str | None = None,
        medication_name: str | None = None,
        dose: str | None = None,
        frequency: str | None = None,
        is_current: bool = True,
        stop_reason: str | None = None,
        recorded_by: str | None = None,
    ) -> Medication:
        if self.patients.get_by_id(patient_id) is None:
            raise ValueError(f"Patient {patient_id} not found")

        if medication_key is not None:
            entry = get_catalog_entry(medication_key)
            if entry is None:
                raise ValueError(f"Unknown medication_key: {medication_key!r}")
            medication_name = entry.display
        elif not medication_name:
            raise ValueError("Either medication_key or medication_name is required")

        if is_current and stop_reason is not None:
            raise ValueError("stop_reason is only valid on a past medication")

        return self.medications.create(
            Medication(
                patient_id=patient_id,
                medication_key=medication_key,
                medication_name=medication_name,
                dose=dose,
                frequency=frequency,
                is_current=is_current,
                stop_reason=stop_reason,
                recorded_by=recorded_by,
            )
        )

    def update_medication(self, medication_id: int, **fields) -> Medication:
        """
        fields may contain dose, frequency, is_current, stop_reason — the
        mutable subset (see MedicationUpdate). Identity fields
        (medication_key/medication_name) don't change on an existing row;
        a different medication is a new row, keeping history honest.
        """
        medication = self.medications.get_by_id(medication_id)
        if medication is None:
            raise ValueError(f"Medication {medication_id} not found")

        allowed = {"dose", "frequency", "is_current", "stop_reason"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Cannot update fields: {sorted(unknown)}")

        will_be_current = fields.get("is_current", medication.is_current)
        if will_be_current:
            if fields.get("stop_reason") is not None:
                raise ValueError("stop_reason is only valid on a past medication")
            fields["stop_reason"] = None  # restarting clears any old reason

        return self.medications.update(medication, **fields)
