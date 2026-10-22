from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.database import get_db
from app.repositories.referral import ReferralRepository
from app.schemas.referral import ReferralCreate, ReferralRead
from app.services.referral_service import ReferralService

router = APIRouter(prefix="/referrals", tags=["referrals"], dependencies=[Depends(get_current_provider)])


@router.post("", response_model=ReferralRead, status_code=201)
def record_referral(payload: ReferralCreate, db: Session = Depends(get_db)):
    """Creates the Referral and its 4-week follow-up Reminder together — see ReferralService."""
    service = ReferralService(db)
    return service.record_referral(**payload.model_dump())


@router.get("/{referral_id}", response_model=ReferralRead)
def get_referral(referral_id: int, db: Session = Depends(get_db)):
    referral = ReferralRepository(db).get_by_id(referral_id)
    if referral is None:
        raise HTTPException(status_code=404, detail="Referral not found")
    return referral


@router.get("", response_model=list[ReferralRead])
def list_referrals(patient_id: int, db: Session = Depends(get_db)):
    return ReferralRepository(db).list_by_patient(patient_id)
