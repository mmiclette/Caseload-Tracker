from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.models.provider import Provider
from app.database import get_db
from app.repositories.episode import EpisodeRepository
from app.repositories.symptom_score import SymptomScoreRepository
from app.repositories.treatment_status import TreatmentStatusRepository
from app.schemas.episode import (
    EpisodeCreate,
    EpisodeRead,
    EpisodeUpdate,
    SymptomScoreRead,
    TreatmentStatusRead,
    TreatmentStatusTransition,
)
from app.services.episode_service import EpisodeService

router = APIRouter(prefix="/episodes", tags=["episodes"], dependencies=[Depends(get_current_provider)])


@router.post("", response_model=EpisodeRead, status_code=201)
def create_episode(
    payload: EpisodeCreate,
    db: Session = Depends(get_db),
    actor: Provider = Depends(get_current_provider),
):
    service = EpisodeService(db)
    try:
        episode = service.create_episode(**payload.model_dump(), actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return episode


@router.get("/{episode_id}", response_model=EpisodeRead)
def get_episode(episode_id: int, db: Session = Depends(get_db)):
    repo = EpisodeRepository(db)
    episode = repo.get_by_id(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@router.get("", response_model=list[EpisodeRead])
def list_episodes(
    patient_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    repo = EpisodeRepository(db)
    if patient_id is not None:
        return repo.list_by_patient(patient_id)
    return repo.list(limit=limit, offset=offset)


@router.patch("/{episode_id}", response_model=EpisodeRead)
def update_episode(
    episode_id: int,
    payload: EpisodeUpdate,
    db: Session = Depends(get_db),
    actor: Provider = Depends(get_current_provider),
):
    # Routed through EpisodeService, not the repository directly, since
    # setting end_date here cascades to a Treatment Status transition to
    # deactivated — see EpisodeService.update_episode.
    service = EpisodeService(db)
    episode = service.episodes.get_by_id(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    updates = payload.model_dump(exclude_unset=True)
    try:
        return service.update_episode(episode_id, actor=actor, **updates)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# --- Symptom Score: as of Phase 2, scores are only ever written through
# ContactService.record_contact (see app/routes/contacts.py) as part of
# recording a visit — there's no standalone POST here any more. This GET
# convenience route survives unchanged: it just lists whatever scores
# accumulated on the episode, from whichever contacts produced them. ---


@router.get("/{episode_id}/scores", response_model=list[SymptomScoreRead])
def list_symptom_scores(episode_id: int, db: Session = Depends(get_db)):
    repo = SymptomScoreRepository(db)
    return repo.list_by_episode(episode_id)


@router.post("/{episode_id}/status", response_model=TreatmentStatusRead, status_code=201)
def transition_treatment_status(
    episode_id: int,
    payload: TreatmentStatusTransition,
    db: Session = Depends(get_db),
    actor: Provider = Depends(get_current_provider),
):
    service = EpisodeService(db)
    episode = service.episodes.get_by_id(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return service.transition_status(
        patient_id=episode.patient_id, episode_id=episode_id, actor=actor,
        **payload.model_dump()
    )


@router.get("/{episode_id}/status/history", response_model=list[TreatmentStatusRead])
def episode_status_history(episode_id: int, db: Session = Depends(get_db)):
    repo = TreatmentStatusRepository(db)
    episode = EpisodeRepository(db).get_by_id(episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return [s for s in repo.list_by_patient(episode.patient_id) if s.episode_id == episode_id]
