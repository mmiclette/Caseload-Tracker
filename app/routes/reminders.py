from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.database import get_db
from app.models.enums import ReminderStatus
from app.repositories.reminder import ReminderRepository
from app.schemas.reminder import ReminderRead, ReminderStatusUpdate
from app.services.reminder_service import ReminderService

router = APIRouter(
    prefix="/reminders", tags=["reminders"], dependencies=[Depends(get_current_provider)]
)

# Referral-triggered reminders are created via POST /referrals now (see
# app/routes/referrals.py and ReferralService.record_referral) — that's
# also what creates the Referral row itself, which this endpoint has no
# way to do. There's no standalone "create a reminder" operation any more,
# same reasoning as Symptom Score only ever arriving through Contact.


@router.get("", response_model=list[ReminderRead])
def list_reminders(
    patient_id: int | None = None,
    status: ReminderStatus | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """
    With no patient_id, this is the BHCM landing-page report: every pending
    reminder, due-date order. status defaults to no filter when patient_id
    is given (a patient's full reminder history), and to pending-only when
    listing across all patients, matching the CTMS's own landing page.
    """
    repo = ReminderRepository(db)
    if patient_id is not None:
        reminders = repo.list_by_patient(patient_id)
        if status is not None:
            reminders = [r for r in reminders if r.status == status]
        return reminders
    if status is not None and status != ReminderStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail="Listing all patients' reminders only supports status=pending; pass patient_id to see other statuses",
        )
    return repo.list_pending(limit=limit, offset=offset)


@router.patch("/{reminder_id}", response_model=ReminderRead)
def update_reminder_status(
    reminder_id: int, payload: ReminderStatusUpdate, db: Session = Depends(get_db)
):
    service = ReminderService(db)
    try:
        if payload.status == ReminderStatus.COMPLETED:
            return service.mark_completed(reminder_id)
        if payload.status == ReminderStatus.DISMISSED:
            return service.mark_dismissed(reminder_id)
        raise HTTPException(status_code=400, detail="status must be completed or dismissed")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
