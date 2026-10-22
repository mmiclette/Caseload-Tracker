from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.models.provider import Provider
from app.database import get_db
from app.repositories.contact import ContactRepository
from app.repositories.symptom_score import SymptomScoreRepository
from app.schemas.contact import ContactCreate, ContactRead
from app.schemas.episode import SymptomScoreRead
from app.services.contact_service import ContactService

router = APIRouter(prefix="/contacts", tags=["contacts"], dependencies=[Depends(get_current_provider)])


@router.post("", response_model=ContactRead, status_code=201)
def record_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    actor: Provider = Depends(get_current_provider),
):
    """
    Records a visit or contact attempt, with any scale scores collected
    during it, in one call — see ContactService.record_contact for the
    baseline, Treatment Status, and psychiatric-review-flag cascades this
    triggers.
    """
    service = ContactService(db)
    try:
        return service.record_contact(
            patient_id=payload.patient_id,
            episode_id=payload.episode_id,
            provider_id=payload.provider_id,
            contact_type=payload.contact_type,
            contact_date=payload.contact_date,
            location=payload.location,
            duration_minutes=payload.duration_minutes,
            discuss_with_psychiatric_consultant=payload.discuss_with_psychiatric_consultant,
            notes_for_consultant=payload.notes_for_consultant,
            notes=payload.notes,
            other_treatments=payload.other_treatments,
            personal_warning_signs=payload.personal_warning_signs,
            stress_reduction_plan=payload.stress_reduction_plan,
            additional_comments=payload.additional_comments,
            medications_confirmation=payload.medications_confirmation,
            scores=[s.model_dump() for s in payload.scores],
            actor=actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    repo = ContactRepository(db)
    contact = repo.get_by_id(contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.get("", response_model=list[ContactRead])
def list_contacts(
    patient_id: int | None = None,
    episode_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    repo = ContactRepository(db)
    if episode_id is not None:
        return repo.list_by_episode(episode_id)
    if patient_id is not None:
        return repo.list_by_patient(patient_id)
    return repo.list(limit=limit, offset=offset)


@router.get("/{contact_id}/scores", response_model=list[SymptomScoreRead])
def list_contact_scores(contact_id: int, db: Session = Depends(get_db)):
    repo = ContactRepository(db)
    if repo.get_by_id(contact_id) is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return SymptomScoreRepository(db).list_by_contact(contact_id)
