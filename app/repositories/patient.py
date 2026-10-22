from sqlalchemy import func, select

from app.models.clinic_assignment import ClinicAssignment
from app.models.patient import Patient
from app.repositories.base import BaseRepository


class PatientRepository(BaseRepository[Patient]):
    model = Patient

    def get_by_mrn(self, mrn: str) -> Patient | None:
        stmt = select(Patient).where(func.lower(Patient.mrn) == func.lower(mrn))
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_clinic(self, clinic_id: str, *, limit: int = 100, offset: int = 0) -> list[Patient]:
        """
        Phase 1 filtered on a single Patient.clinic_id column. Phase 2
        replaced that column with ClinicAssignment (a patient can belong to
        more than one clinic over time), so this now joins through it and
        only counts a patient as "at" a clinic while that assignment is
        current (service_end_date is null).
        """
        stmt = (
            select(Patient)
            .join(ClinicAssignment, ClinicAssignment.patient_id == Patient.patient_id)
            .where(
                ClinicAssignment.clinic_id == clinic_id,
                ClinicAssignment.service_end_date.is_(None),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).scalars().all())
