from sqlalchemy import select

from app.models.medication import Medication
from app.repositories.base import BaseRepository


class MedicationRepository(BaseRepository[Medication]):
    model = Medication

    def list_by_patient(self, patient_id: int) -> list[Medication]:
        """Current medications first, then past, alphabetical within each."""
        stmt = (
            select(Medication)
            .where(Medication.patient_id == patient_id)
            .order_by(Medication.is_current.desc(), Medication.medication_name)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_current_by_patient(self, patient_id: int) -> list[Medication]:
        stmt = (
            select(Medication)
            .where(Medication.patient_id == patient_id, Medication.is_current.is_(True))
            .order_by(Medication.medication_name)
        )
        return list(self.db.execute(stmt).scalars().all())
