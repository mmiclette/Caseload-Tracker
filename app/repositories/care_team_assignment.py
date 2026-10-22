from sqlalchemy import select

from app.models.care_team_assignment import CareTeamAssignment
from app.repositories.base import BaseRepository


class CareTeamAssignmentRepository(BaseRepository[CareTeamAssignment]):
    model = CareTeamAssignment

    def list_by_patient(self, patient_id: int) -> list[CareTeamAssignment]:
        stmt = select(CareTeamAssignment).where(CareTeamAssignment.patient_id == patient_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_current_by_patient(self, patient_id: int) -> list[CareTeamAssignment]:
        """Assignments with no service_end_date — the CTMS's "Current Providers" table."""
        stmt = select(CareTeamAssignment).where(
            CareTeamAssignment.patient_id == patient_id,
            CareTeamAssignment.service_end_date.is_(None),
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_current_provider_ids(self) -> list[int]:
        """Every Provider with at least one current care team assignment — used to enumerate groups for Caseload Statistics."""
        stmt = (
            select(CareTeamAssignment.provider_id)
            .distinct()
            .where(CareTeamAssignment.service_end_date.is_(None))
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_patient_ids_for_provider(self, provider_id: int) -> list[int]:
        """
        Patients currently on a given Provider's care team — this is what
        the Active Patients report's "filterable by ... provider" note in
        CLAUDE.md means (so one Care Manager can cover another's caseload
        during leave).
        """
        stmt = select(CareTeamAssignment.patient_id).where(
            CareTeamAssignment.provider_id == provider_id,
            CareTeamAssignment.service_end_date.is_(None),
        )
        return list(self.db.execute(stmt).scalars().all())
