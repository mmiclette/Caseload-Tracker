from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.database import get_db
from app.models.care_team_assignment import CareTeamAssignment
from app.repositories.care_team_assignment import CareTeamAssignmentRepository
from app.schemas.care_team_assignment import (
    CareTeamAssignmentCreate,
    CareTeamAssignmentRead,
    CareTeamAssignmentUpdate,
)

router = APIRouter(
    prefix="/care-team-assignments",
    tags=["care-team-assignments"],
    dependencies=[Depends(get_current_provider)],
)


@router.post("", response_model=CareTeamAssignmentRead, status_code=201)
def create_care_team_assignment(payload: CareTeamAssignmentCreate, db: Session = Depends(get_db)):
    repo = CareTeamAssignmentRepository(db)
    return repo.create(CareTeamAssignment(**payload.model_dump()))


@router.get("", response_model=list[CareTeamAssignmentRead])
def list_care_team_assignments(
    patient_id: int | None = None,
    current_only: bool = False,
    db: Session = Depends(get_db),
):
    repo = CareTeamAssignmentRepository(db)
    if patient_id is None:
        raise HTTPException(status_code=400, detail="patient_id is required")
    if current_only:
        return repo.list_current_by_patient(patient_id)
    return repo.list_by_patient(patient_id)


@router.patch("/{care_team_assignment_id}", response_model=CareTeamAssignmentRead)
def update_care_team_assignment(
    care_team_assignment_id: int, payload: CareTeamAssignmentUpdate, db: Session = Depends(get_db)
):
    repo = CareTeamAssignmentRepository(db)
    assignment = repo.get_by_id(care_team_assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Care team assignment not found")
    updates = payload.model_dump(exclude_unset=True)
    return repo.update(assignment, **updates)
