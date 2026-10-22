from datetime import date

from sqlalchemy import or_, select

from app.models.episode import EpisodeOfCare
from app.repositories.base import BaseRepository


class EpisodeRepository(BaseRepository[EpisodeOfCare]):
    model = EpisodeOfCare

    def list_open_during(self, start: date, end: date) -> list[EpisodeOfCare]:
        """
        Every episode open at any point within [start, end] — the
        historical generalization of get_open_episode's "right now," used
        by CoCM Quality Metrics to build each month's caseload snapshot
        (see app/services/quality_metrics.py).
        """
        stmt = select(EpisodeOfCare).where(
            EpisodeOfCare.start_date <= end,
            or_(EpisodeOfCare.end_date.is_(None), EpisodeOfCare.end_date >= start),
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_completed_in_year(self, year: int) -> list[EpisodeOfCare]:
        """
        Every episode closed during a calendar year, across all patients —
        used by Completed Episode Statistics. Uses a plain date-range
        comparison rather than EXTRACT(year, ...) so this stays portable
        without depending on either dialect's date-function support.
        """
        stmt = select(EpisodeOfCare).where(
            EpisodeOfCare.end_date.is_not(None),
            EpisodeOfCare.end_date >= date(year, 1, 1),
            EpisodeOfCare.end_date <= date(year, 12, 31),
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_patient(self, patient_id: int) -> list[EpisodeOfCare]:
        stmt = (
            select(EpisodeOfCare)
            .where(EpisodeOfCare.patient_id == patient_id)
            .order_by(EpisodeOfCare.start_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_open_episode(self, patient_id: int) -> EpisodeOfCare | None:
        """The patient's most recent episode with no end_date, if any."""
        stmt = (
            select(EpisodeOfCare)
            .where(EpisodeOfCare.patient_id == patient_id, EpisodeOfCare.end_date.is_(None))
            .order_by(EpisodeOfCare.start_date.desc())
        )
        return self.db.execute(stmt).scalars().first()
