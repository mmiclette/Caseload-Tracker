from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.core.security import hash_password
from app.database import get_db
from app.models.provider import Provider
from app.repositories.provider import ProviderRepository
from app.schemas.provider import ProviderCreate, ProviderRead, ProviderUpdate

router = APIRouter(prefix="/providers", tags=["providers"], dependencies=[Depends(get_current_provider)])


@router.post("", response_model=ProviderRead, status_code=201)
def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)):
    repo = ProviderRepository(db)
    if payload.email is not None and repo.get_by_email(payload.email) is not None:
        raise HTTPException(status_code=409, detail=f"Email '{payload.email}' already exists")
    data = payload.model_dump()
    password = data.pop("password", None)
    provider = Provider(**data)
    if password:
        provider.hashed_password = hash_password(password)
    return repo.create(provider)


@router.get("/{provider_id}", response_model=ProviderRead)
def get_provider(provider_id: int, db: Session = Depends(get_db)):
    repo = ProviderRepository(db)
    provider = repo.get_by_id(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.get("", response_model=list[ProviderRead])
def list_providers(
    role: str | None = None, limit: int = 100, offset: int = 0, db: Session = Depends(get_db)
):
    repo = ProviderRepository(db)
    if role:
        return repo.list_by_role(role)
    return repo.list(limit=limit, offset=offset)


@router.patch("/{provider_id}", response_model=ProviderRead)
def update_provider(provider_id: int, payload: ProviderUpdate, db: Session = Depends(get_db)):
    repo = ProviderRepository(db)
    provider = repo.get_by_id(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    updates = payload.model_dump(exclude_unset=True)
    return repo.update(provider, **updates)
