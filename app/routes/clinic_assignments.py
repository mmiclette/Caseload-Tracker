from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.database import get_db
from app.models.clinic_assignment import ClinicAssignment
from app.repositories.clinic_assignment import ClinicAssignmentRepository
from app.schemas.clinic_assignment import (
    ClinicAssignmentCreate,
    ClinicAssignmentRead,
    ClinicAssignmentUpdate,
)

router = APIRouter(
    prefix="/clinic-assignments",
    tags=["clinic-assignments"],
    dependencies=[Depends(get_current_provider)],
)


@router.post("", response_model=ClinicAssignmentRead, status_code=201)
def create_clinic_assignment(payload: ClinicAssignmentCreate, db: Session = Depends(get_db)):
    repo = ClinicAssignmentRepository(db)
    return repo.create(ClinicAssignment(**payload.model_dump()))


@router.get("", response_model=list[ClinicAssignmentRead])
def list_clinic_assignments(
    patient_id: int | None = None,
    current_only: bool = False,
    db: Session = Depends(get_db),
):
    repo = ClinicAssignmentRepository(db)
    if patient_id is None:
        raise HTTPException(status_code=400, detail="patient_id is required")
    if current_only:
        return repo.list_current_by_patient(patient_id)
    return repo.list_by_patient(patient_id)


@router.patch("/{clinic_assignment_id}", response_model=ClinicAssignmentRead)
def update_clinic_assignment(
    clinic_assignment_id: int, payload: ClinicAssignmentUpdate, db: Session = Depends(get_db)
):
    repo = ClinicAssignmentRepository(db)
    assignment = repo.get_by_id(clinic_assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Clinic assignment not found")
    updates = payload.model_dump(exclude_unset=True)
    return repo.update(assignment, **updates)
