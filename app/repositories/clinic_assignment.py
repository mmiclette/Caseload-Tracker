from sqlalchemy import select

from app.models.clinic_assignment import ClinicAssignment
from app.repositories.base import BaseRepository


class ClinicAssignmentRepository(BaseRepository[ClinicAssignment]):
    model = ClinicAssignment

    def list_by_patient(self, patient_id: int) -> list[ClinicAssignment]:
        stmt = select(ClinicAssignment).where(ClinicAssignment.patient_id == patient_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_current_by_patient(self, patient_id: int) -> list[ClinicAssignment]:
        stmt = select(ClinicAssignment).where(
            ClinicAssignment.patient_id == patient_id,
            ClinicAssignment.service_end_date.is_(None),
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_current_clinic_ids(self) -> list[str]:
        """Every clinic_id with at least one current assignment — used to enumerate groups for Caseload Statistics."""
        stmt = (
            select(ClinicAssignment.clinic_id)
            .distinct()
            .where(ClinicAssignment.service_end_date.is_(None))
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_patient_ids_for_clinic(self, clinic_id: str) -> list[int]:
        """
        Patients currently assigned to a clinic — this is what replaces
        Phase 1's Patient.clinic_id filter (see PatientRepository.list_by_clinic).
        """
        stmt = select(ClinicAssignment.patient_id).where(
            ClinicAssignment.clinic_id == clinic_id,
            ClinicAssignment.service_end_date.is_(None),
        )
        return list(self.db.execute(stmt).scalars().all())
