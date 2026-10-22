from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.database import get_db
from app.repositories.medication import MedicationRepository
from app.schemas.medication import (
    CatalogEntryRead,
    MedicationCreate,
    MedicationRead,
    MedicationUpdate,
)
from app.services.medication_catalog import search_catalog
from app.services.medication_service import MedicationService

router = APIRouter(
    prefix="/medications", tags=["medications"], dependencies=[Depends(get_current_provider)]
)


@router.get("/catalog", response_model=list[CatalogEntryRead])
def search_medication_catalog(
    q: str = Query("", description="Search-as-you-type over medication names"),
    limit: int = Query(20, ge=1, le=100),
):
    """Backs the med picker: matching catalog entries with their dose options."""
    return search_catalog(q, limit=limit)


@router.post("", response_model=MedicationRead, status_code=201)
def record_medication(payload: MedicationCreate, db: Session = Depends(get_db)):
    service = MedicationService(db)
    try:
        return service.record_medication(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("", response_model=list[MedicationRead])
def list_medications(patient_id: int, db: Session = Depends(get_db)):
    return MedicationRepository(db).list_by_patient(patient_id)


@router.get("/{medication_id}", response_model=MedicationRead)
def get_medication(medication_id: int, db: Session = Depends(get_db)):
    medication = MedicationRepository(db).get_by_id(medication_id)
    if medication is None:
        raise HTTPException(status_code=404, detail="Medication not found")
    return medication


@router.patch("/{medication_id}", response_model=MedicationRead)
def update_medication(
    medication_id: int, payload: MedicationUpdate, db: Session = Depends(get_db)
):
    service = MedicationService(db)
    try:
        return service.update_medication(medication_id, **payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        status = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc))
