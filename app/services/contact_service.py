"""
Contact service.

This is the Phase 2 replacement for Phase 1's EpisodeService.add_symptom_score
— it's the single place a visit (or a failed outreach attempt) gets
recorded, matching the CTMS's own contact-recording form: one save action
for the visit date, every scale score collected that day, and the
psychiatric-consultant checkbox, all together.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.enums import AuditAction, ContactType, TreatmentStatusEnum
from app.models.symptom_score import SymptomScore
from app.repositories.contact import ContactRepository
from app.repositories.patient import PatientRepository
from app.repositories.symptom_score import SymptomScoreRepository
from app.services.audit import AuditService
from app.services.episode_service import EpisodeService
from app.services.reminder_service import ReminderService


class ContactService:
    def __init__(self, db: Session):
        self.db = db
        self.contacts = ContactRepository(db)
        self.scores = SymptomScoreRepository(db)
        self.patients = PatientRepository(db)
        self.episode_service = EpisodeService(db)
        self.reminder_service = ReminderService(db)
        self.audit = AuditService(db)

    def record_contact(
        self,
        *,
        patient_id: int,
        contact_type: ContactType,
        contact_date: date,
        episode_id: int | None = None,
        provider_id: int | None = None,
        location=None,
        duration_minutes: int | None = None,
        discuss_with_psychiatric_consultant: bool = False,
        notes_for_consultant: str | None = None,
        notes: str | None = None,
        other_treatments: str | None = None,
        personal_warning_signs: str | None = None,
        stress_reduction_plan: str | None = None,
        additional_comments: str | None = None,
        medications_confirmation=None,
        scores: list[dict] | None = None,
        actor=None,
    ) -> Contact:
        scores = scores or []

        if contact_type in (ContactType.CONTACT_ATTEMPT, ContactType.CARE_TEAM_COLLABORATION) and scores:
            raise ValueError(f"A {contact_type.value} cannot carry Symptom Scores")
        if scores and episode_id is None:
            raise ValueError("Recording scores requires episode_id")

        # The Relapse Prevention Plan fields only exist on the RPP form —
        # accepting them on a follow-up would silently create plan content
        # no screen ever shows (see app/models/contact.py).
        rpp_fields = {
            "other_treatments": other_treatments,
            "personal_warning_signs": personal_warning_signs,
            "stress_reduction_plan": stress_reduction_plan,
            "additional_comments": additional_comments,
            "medications_confirmation": medications_confirmation,
        }
        if contact_type != ContactType.RELAPSE_PREVENTION_PLAN:
            supplied = sorted(k for k, v in rpp_fields.items() if v is not None)
            if supplied:
                raise ValueError(
                    f"{supplied} only apply to a relapse_prevention_plan contact, "
                    f"not {contact_type.value}"
                )

        attempt_number = (
            self.contacts.next_attempt_number(patient_id)
            if contact_type == ContactType.CONTACT_ATTEMPT
            else None
        )

        contact = self.contacts.create(
            Contact(
                patient_id=patient_id,
                episode_id=episode_id,
                provider_id=provider_id,
                contact_type=contact_type,
                contact_date=contact_date,
                location=location,
                duration_minutes=duration_minutes,
                discuss_with_psychiatric_consultant=discuss_with_psychiatric_consultant,
                notes_for_consultant=notes_for_consultant,
                notes=notes,
                other_treatments=other_treatments,
                personal_warning_signs=personal_warning_signs,
                stress_reduction_plan=stress_reduction_plan,
                additional_comments=additional_comments,
                medications_confirmation=medications_confirmation,
                attempt_number=attempt_number,
            )
        )

        measure_types_recorded = set()
        for score_input in scores:
            score = self.scores.create(
                SymptomScore(
                    patient_id=patient_id,
                    episode_id=episode_id,
                    contact_id=contact.contact_id,
                    measure_type=score_input["measure_type"],
                    score_value=score_input["score_value"],
                    score_date=contact_date,
                    recorded_by=score_input.get("recorded_by"),
                )
            )
            measure_types_recorded.add(score.measure_type)
            self.audit.record(
                action=AuditAction.SCORE_RECORDED,
                entity_type="symptom_score",
                entity_id=score.score_id,
                patient_id=patient_id,
                actor=actor,
                field=score.measure_type.value,
                new_value=score.score_value,
                context=f"recorded at {contact_type.value} contact {contact.contact_id}",
            )

        for measure_type in measure_types_recorded:
            self.episode_service.recompute_baseline(episode_id, measure_type)

        # Cascade: an RPP contact drops the follow-up cadence from every 2
        # weeks to every 4 weeks automatically, per the CTMS — see
        # CLAUDE.md and the equivalent guard in EpisodeService.update_episode.
        if contact_type == ContactType.RELAPSE_PREVENTION_PLAN:
            current = self.episode_service.get_current_status(patient_id)
            if current is None or current.status != TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN:
                self.episode_service.transition_status(
                    patient_id=patient_id,
                    episode_id=episode_id,
                    status=TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN,
                    status_changed_date=contact_date,
                    actor=actor,
                    audit_context=(
                        f"cascade from relapse prevention plan contact {contact.contact_id}"
                    ),
                )

        # Cascade: checking "discuss with psychiatric consultant" is the
        # literal mechanism that lights the yellow flag. This only ever
        # turns the flag ON — only a recorded Consultation turns it off
        # (see ConsultationService), matching the CTMS's own description.
        if discuss_with_psychiatric_consultant:
            patient = self.patients.get_by_id(patient_id)
            if patient is not None and not patient.needs_psychiatric_review:
                self.patients.update(patient, needs_psychiatric_review=True)
                self.audit.record_flag_change(
                    patient_id=patient_id,
                    field="needs_psychiatric_review",
                    old_value=False,
                    new_value=True,
                    actor=actor,
                    context=(
                        "discuss-with-consultant checked on contact "
                        f"{contact.contact_id}"
                    ),
                )

        # Cascade: recompute the appointment reminder's due date off this
        # contact (a completed contact resets the cadence clock; a
        # contact_attempt does not — see ReminderService and
        # ContactRepository.most_recent_completed_for_patient).
        self.reminder_service.recompute_appointment_reminder(patient_id)

        return contact
