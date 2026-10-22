from sqlalchemy import select

from app.models.symptom_score import SymptomScore
from app.repositories.base import BaseRepository


class SymptomScoreRepository(BaseRepository[SymptomScore]):
    model = SymptomScore

    def list_by_episode(self, episode_id: int) -> list[SymptomScore]:
        stmt = (
            select(SymptomScore)
            .where(SymptomScore.episode_id == episode_id)
            .order_by(SymptomScore.score_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_patient(self, patient_id: int) -> list[SymptomScore]:
        stmt = (
            select(SymptomScore)
            .where(SymptomScore.patient_id == patient_id)
            .order_by(SymptomScore.score_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_contact(self, contact_id: int) -> list[SymptomScore]:
        stmt = select(SymptomScore).where(SymptomScore.contact_id == contact_id)
        return list(self.db.execute(stmt).scalars().all())
