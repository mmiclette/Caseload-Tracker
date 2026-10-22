from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.database import get_db
from app.models.enums import ProfileSection
from app.repositories.profile_entry import ProfileEntryRepository
from app.schemas.profile_entry import (
    ProfileEntryCreate,
    ProfileEntryRead,
    ProfileSectionRead,
)
from app.services.profile_entry_service import (
    SECTION_SUB_FIELD_SUGGESTIONS,
    ProfileEntryService,
)

router = APIRouter(
    prefix="/profile-entries",
    tags=["profile-entries"],
    dependencies=[Depends(get_current_provider)],
)

# NOTE: no PATCH and no DELETE here, on purpose — ProfileEntry is
# append-only (see app/models/profile_entry.py). A correction is a new
# entry that supersedes the old one at display time.


@router.get("/sections", response_model=list[ProfileSectionRead])
def list_sections():
    """The click-to-add picker: each section with its default sub-field suggestions."""
    return [
        ProfileSectionRead(section=section, sub_field_suggestions=suggestions)
        for section, suggestions in SECTION_SUB_FIELD_SUGGESTIONS.items()
    ]


@router.post("", response_model=ProfileEntryRead, status_code=201)
def record_profile_entry(payload: ProfileEntryCreate, db: Session = Depends(get_db)):
    service = ProfileEntryService(db)
    try:
        return service.record_entry(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("", response_model=list[ProfileEntryRead])
def list_profile_entries(
    patient_id: int,
    section: ProfileSection | None = None,
    db: Session = Depends(get_db),
):
    return ProfileEntryRepository(db).list_by_patient(patient_id, section=section)


@router.get("/{profile_entry_id}", response_model=ProfileEntryRead)
def get_profile_entry(profile_entry_id: int, db: Session = Depends(get_db)):
    entry = ProfileEntryRepository(db).get_by_id(profile_entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Profile entry not found")
    return entry
