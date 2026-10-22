from sqlalchemy import select

from app.models.referral import Referral
from app.repositories.base import BaseRepository


class ReferralRepository(BaseRepository[Referral]):
    model = Referral

    def list_by_patient(self, patient_id: int) -> list[Referral]:
        stmt = (
            select(Referral)
            .where(Referral.patient_id == patient_id)
            .order_by(Referral.referral_date)
        )
        return list(self.db.execute(stmt).scalars().all())
