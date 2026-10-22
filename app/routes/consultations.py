from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.models.provider import Provider
from app.database import get_db
from app.repositories.consultation import ConsultationRepository
from app.schemas.consultation import ConsultationCreate, ConsultationRead
from app.services.consultation_service import ConsultationService

router = APIRouter(
    prefix="/consultations", tags=["consultations"], dependencies=[Depends(get_current_provider)]
)


@router.post("", response_model=ConsultationRead, status_code=201)
def record_consultation(
    payload: ConsultationCreate,
    db: Session = Depends(get_db),
    actor: Provider = Depends(get_current_provider),
):
    """
    Recording a Consultation is what clears Patient.needs_psychiatric_review
    (or re-sets it, if this consultation itself flags a future review) — see
    ConsultationService.record_consultation for the cascade.
    """
    service = ConsultationService(db)
    return service.record_consultation(**payload.model_dump(), actor=actor)


@router.get("/{consultation_id}", response_model=ConsultationRead)
def get_consultation(consultation_id: int, db: Session = Depends(get_db)):
    repo = ConsultationRepository(db)
    consultation = repo.get_by_id(consultation_id)
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


@router.get("", response_model=list[ConsultationRead])
def list_consultations(patient_id: int | None = None, db: Session = Depends(get_db)):
    repo = ConsultationRepository(db)
    if patient_id is None:
        raise HTTPException(status_code=400, detail="patient_id is required")
    return repo.list_by_patient(patient_id)
