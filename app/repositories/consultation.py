from datetime import date

from sqlalchemy import select

from app.models.consultation import Consultation
from app.repositories.base import BaseRepository


class ConsultationRepository(BaseRepository[Consultation]):
    model = Consultation

    def list_by_patient(self, patient_id: int) -> list[Consultation]:
        stmt = (
            select(Consultation)
            .where(Consultation.patient_id == patient_id)
            .order_by(Consultation.consultation_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_patient_ids_with_timed_consultation_between(self, start: date, end: date) -> list[int]:
        """
        Distinct patients with at least one timed Consultation in
        [start, end] — the consultation-side twin of
        ContactRepository.list_patient_ids_with_billable_contact_between,
        used by Monthly Time Tracker (consultant minutes are billable
        CoCM time).
        """
        stmt = (
            select(Consultation.patient_id)
            .distinct()
            .where(
                Consultation.duration_minutes.is_not(None),
                Consultation.consultation_date >= start,
                Consultation.consultation_date <= end,
            )
        )
        return list(self.db.execute(stmt).scalars().all())
