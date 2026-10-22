"""
Consultation service.

Recording a Consultation is what clears Patient.needs_psychiatric_review —
the CTMS: "The yellow flag on the Caseload List will automatically turn
off once that's done." If this same consultation also flags the patient
for a future review, the flag is immediately re-set — "reviewed today" and
"review again next time" are different things, and a caller setting
flagged_for_next_review=True clearly wants the flag back on, not cleared.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.consultation import Consultation
from app.repositories.consultation import ConsultationRepository
from app.models.enums import AuditAction
from app.repositories.patient import PatientRepository
from app.services.audit import AuditService


class ConsultationService:
    def __init__(self, db: Session):
        self.db = db
        self.consultations = ConsultationRepository(db)
        self.patients = PatientRepository(db)
        self.audit = AuditService(db)

    def record_consultation(
        self,
        *,
        patient_id: int,
        consultation_date: date,
        provider_id: int | None = None,
        duration_minutes: int | None = None,
        recommendations_forwarded: bool = False,
        flagged_for_next_review: bool = False,
        flag_reason: str | None = None,
        notes: str | None = None,
        actor=None,
    ) -> Consultation:
        consultation = self.consultations.create(
            Consultation(
                patient_id=patient_id,
                provider_id=provider_id,
                consultation_date=consultation_date,
                duration_minutes=duration_minutes,
                recommendations_forwarded=recommendations_forwarded,
                flagged_for_next_review=flagged_for_next_review,
                flag_reason=flag_reason,
                notes=notes,
            )
        )

        patient = self.patients.get_by_id(patient_id)
        if patient is not None:
            was_flagged = patient.needs_psychiatric_review
            self.patients.update(patient, needs_psychiatric_review=flagged_for_next_review)
            if was_flagged != flagged_for_next_review:
                self.audit.record_flag_change(
                    patient_id=patient_id,
                    field="needs_psychiatric_review",
                    old_value=was_flagged,
                    new_value=flagged_for_next_review,
                    actor=actor,
                    context=(
                        f"consultation {consultation.consultation_id} recorded"
                        + (
                            " and flagged the patient for another review"
                            if flagged_for_next_review
                            else ""
                        )
                    ),
                )

        return consultation
