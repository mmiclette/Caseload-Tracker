from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.database import get_db
from app.models.enums import AuditAction
from app.models.provider import Provider
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate, PatientRead, PatientUpdate
from app.services.audit import AuditService

router = APIRouter(prefix="/patients", tags=["patients"], dependencies=[Depends(get_current_provider)])

# Which PatientUpdate fields are the flags CLAUDE.md's PHI rule names
# explicitly. Each gets its own flag_set/flag_cleared audit entry rather
# than being lumped into a generic "patient updated", because "who raised
# the safety flag, and when" is the question an audit trail exists to
# answer.
FLAG_FIELDS = ("needs_psychiatric_review", "safety_risk", "custom_flag_active")


@router.post("", response_model=PatientRead, status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    repo = PatientRepository(db)
    if repo.get_by_mrn(payload.mrn) is not None:
        raise HTTPException(status_code=409, detail="A patient with that MRN already exists")
    from app.models.patient import Patient

    return repo.create(Patient(**payload.model_dump()))


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    patient = PatientRepository(db).get_by_id(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@router.get("", response_model=list[PatientRead])
def list_patients(
    clinic_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    repo = PatientRepository(db)
    if clinic_id is not None:
        return repo.list_by_clinic(clinic_id)
    return repo.list(limit=limit, offset=offset)


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    actor: Provider = Depends(get_current_provider),
):
    """
    Audited: every flag change gets its own entry, deactivation gets its
    own, and any other field change is recorded as patient_updated with the
    before and after values. `actor` resolves from the same dependency the
    router already enforces, and FastAPI caches it per request, so binding
    it here costs no extra lookup.
    """
    repo = PatientRepository(db)
    patient = repo.get_by_id(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    updates = payload.model_dump(exclude_unset=True)
    before = {field: getattr(patient, field) for field in updates}
    updated = repo.update(patient, **updates)

    audit = AuditService(db)
    for field, new_value in updates.items():
        old_value = before[field]
        if old_value == new_value:
            continue  # a no-op write is not a change worth recording
        if field in FLAG_FIELDS:
            audit.record_flag_change(
                patient_id=patient_id,
                field=field,
                old_value=bool(old_value),
                new_value=bool(new_value),
                actor=actor,
            )
        elif field == "deactivation_date" and new_value is not None:
            audit.record(
                action=AuditAction.PATIENT_DEACTIVATED,
                entity_type="patient",
                entity_id=patient_id,
                patient_id=patient_id,
                actor=actor,
                field=field,
                old_value=old_value,
                new_value=new_value,
            )
        else:
            audit.record(
                action=AuditAction.PATIENT_UPDATED,
                entity_type="patient",
                entity_id=patient_id,
                patient_id=patient_id,
                actor=actor,
                field=field,
                old_value=old_value,
                new_value=new_value,
            )
    return updated
