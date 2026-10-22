from sqlalchemy import select

from app.models.treatment_status import TreatmentStatus
from app.repositories.base import BaseRepository


class TreatmentStatusRepository(BaseRepository[TreatmentStatus]):
    model = TreatmentStatus

    def list_by_patient(self, patient_id: int) -> list[TreatmentStatus]:
        stmt = (
            select(TreatmentStatus)
            .where(TreatmentStatus.patient_id == patient_id)
            .order_by(TreatmentStatus.status_changed_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_current(self, patient_id: int) -> TreatmentStatus | None:
        """Most recent status transition for a patient, by status_changed_date."""
        stmt = (
            select(TreatmentStatus)
            .where(TreatmentStatus.patient_id == patient_id)
            .order_by(
                TreatmentStatus.status_changed_date.desc(),
                TreatmentStatus.treatment_status_id.desc(),
            )
        )
        return self.db.execute(stmt).scalars().first()
