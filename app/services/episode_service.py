"""
Episode of Care service.

Treatment Status is written and read through this service — routes never
poke at that table directly. As of Phase 2, Symptom Score is written
through ContactService instead (a score only ever exists as part of a
Contact now); this service still owns baseline recomputation, since that's
Episode-level bookkeeping, and exposes it as recompute_baseline() for
ContactService to call after it inserts scores.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.episode import EpisodeOfCare
from app.models.enums import AuditAction, ConditionType, TreatmentStatusEnum
from app.models.treatment_status import TreatmentStatus
from app.repositories.episode import EpisodeRepository
from app.repositories.symptom_score import SymptomScoreRepository
from app.repositories.treatment_status import TreatmentStatusRepository
from app.services.audit import AuditService
from app.services.reminder_service import ReminderService
from app.services.scoring import CONDITION_MEASURES, ScoreRecord, determine_baseline


def _validate_diagnoses(
    primary: ConditionType | None, secondary: ConditionType | None
) -> None:
    if secondary is not None and secondary == primary:
        raise ValueError("secondary_diagnosis must differ from primary_diagnosis")
    if secondary is not None and primary is None:
        raise ValueError("secondary_diagnosis requires a primary_diagnosis")


class EpisodeService:
    def __init__(self, db: Session):
        self.db = db
        self.episodes = EpisodeRepository(db)
        self.scores = SymptomScoreRepository(db)
        self.statuses = TreatmentStatusRepository(db)
        self.reminder_service = ReminderService(db)
        self.audit = AuditService(db)

    def create_episode(
        self,
        *,
        patient_id: int,
        start_date: date,
        primary_diagnosis: ConditionType | None = None,
        secondary_diagnosis: ConditionType | None = None,
        set_active_status: bool = True,
        actor=None,
    ) -> EpisodeOfCare:
        _validate_diagnoses(primary_diagnosis, secondary_diagnosis)
        episode = self.episodes.create(
            EpisodeOfCare(
                patient_id=patient_id,
                start_date=start_date,
                primary_diagnosis=primary_diagnosis,
                secondary_diagnosis=secondary_diagnosis,
            )
        )
        self.audit.record(
            action=AuditAction.EPISODE_OPENED,
            entity_type="episode_of_care",
            entity_id=episode.episode_id,
            patient_id=patient_id,
            actor=actor,
            field="start_date",
            new_value=start_date,
            context=(
                f"primary={primary_diagnosis.value if primary_diagnosis else 'none'}"
                f", secondary={secondary_diagnosis.value if secondary_diagnosis else 'none'}"
            ),
        )
        if set_active_status:
            self.transition_status(
                patient_id=patient_id,
                episode_id=episode.episode_id,
                status=TreatmentStatusEnum.ACTIVE_TREATMENT,
                status_changed_date=start_date,
                actor=actor,
                audit_context="cascade from opening the episode of care",
            )
            # Cascade: entering active_treatment is what starts the
            # reminder clock — the initial-assessment-scheduling reminder,
            # due within 7 days of enrollment (see ReminderService).
            self.reminder_service.recompute_appointment_reminder(patient_id)
        return episode

    def recompute_baseline(self, episode_id: int, measure_type) -> EpisodeOfCare:
        """
        Recomputes an episode's baseline (not just set-once) from every
        same-measure_type score currently on record, via
        app.services.scoring.determine_baseline — the single place baseline
        logic lives. Called by ContactService after it inserts new scores,
        so a score entered out of order (e.g. a backdated correction with
        an earlier score_date than what's already on file) still correctly
        becomes the baseline.

        An episode carries one baseline (one measure_type/score/date
        triple). Once a baseline measure_type is set, only scores of that
        same measure_type are considered for future baseline
        recomputation — see the "ambiguous" note in CLAUDE.md about
        episodes that track both PHQ-9 and GAD-7 — with one exception: when
        the episode has a primary_diagnosis and the established baseline's
        measure is NOT one of that diagnosis's mapped measures
        (CONDITION_MEASURES) but the incoming score's measure IS, the
        baseline re-anchors onto the primary-mapped measure. This is the
        soft consistency rule: if primary is anxiety, the index baseline
        should be GAD-7 even when a PHQ-9 happened to be recorded first.
        Within the same diagnosis's candidates (PHQ-9 vs pediatric SMFQ),
        first-established still wins.
        """
        episode = self.episodes.get_by_id(episode_id)
        if episode is None:
            raise ValueError(f"Episode {episode_id} not found")

        if episode.baseline_measure_type is not None and episode.baseline_measure_type != measure_type:
            candidates = (
                CONDITION_MEASURES[episode.primary_diagnosis]
                if episode.primary_diagnosis is not None
                else None
            )
            primary_wins = (
                candidates is not None
                and measure_type in candidates
                and episode.baseline_measure_type not in candidates
            )
            if not primary_wins:
                return episode

        same_measure_scores = [
            ScoreRecord(
                measure_type=s.measure_type,
                score_value=s.score_value,
                score_date=s.score_date,
            )
            for s in self.scores.list_by_episode(episode_id)
            if s.measure_type == measure_type
        ]
        baseline = determine_baseline(same_measure_scores)
        if baseline is not None and (
            episode.baseline_measure_type != baseline.measure_type
            or episode.baseline_score != baseline.score_value
            or episode.baseline_date != baseline.score_date
        ):
            episode = self.episodes.update(
                episode,
                baseline_measure_type=baseline.measure_type,
                baseline_score=baseline.score_value,
                baseline_date=baseline.score_date,
            )
        return episode

    def update_episode(self, episode_id: int, *, actor=None, **updates) -> EpisodeOfCare:
        """
        Updates an episode and cascades to Treatment Status when
        appropriate. Setting end_date on an episode that was previously
        open is what the CTMS calls "deactivating" a patient, and per that
        behavior, it automatically transitions Treatment Status to
        deactivated rather than requiring a second explicit call — same
        reasoning as the RPP cascade in ContactService.record_contact.
        """
        episode = self.episodes.get_by_id(episode_id)
        if episode is None:
            raise ValueError(f"Episode {episode_id} not found")

        if "primary_diagnosis" in updates or "secondary_diagnosis" in updates:
            _validate_diagnoses(
                updates.get("primary_diagnosis", episode.primary_diagnosis),
                updates.get("secondary_diagnosis", episode.secondary_diagnosis),
            )

        is_newly_closed = (
            "end_date" in updates
            and updates["end_date"] is not None
            and episode.end_date is None
        )

        previous_end_date = episode.end_date
        updated = self.episodes.update(episode, **updates)

        if is_newly_closed:
            self.audit.record(
                action=AuditAction.EPISODE_CLOSED,
                entity_type="episode_of_care",
                entity_id=episode_id,
                patient_id=updated.patient_id,
                actor=actor,
                field="end_date",
                old_value=previous_end_date,
                new_value=updated.end_date,
                context=(
                    f"end_reason={updated.end_reason.value}"
                    if updated.end_reason
                    else "end_reason not recorded"
                ),
            )
            current = self.get_current_status(episode.patient_id)
            if current is None or current.status != TreatmentStatusEnum.DEACTIVATED:
                self.transition_status(
                    patient_id=episode.patient_id,
                    episode_id=episode_id,
                    status=TreatmentStatusEnum.DEACTIVATED,
                    status_changed_date=updated.end_date,
                    actor=actor,
                    audit_context="cascade from closing the episode of care",
                )
                # Cascade: a deactivated patient has nothing pending — see
                # ReminderService.recompute_appointment_reminder, which
                # dismisses any pending appointment reminder once status is
                # deactivated.
                self.reminder_service.recompute_appointment_reminder(episode.patient_id)

        return updated

    def transition_status(
        self,
        *,
        patient_id: int,
        status: TreatmentStatusEnum,
        status_changed_date: date,
        episode_id: int | None = None,
        changed_by: str | None = None,
        notes: str | None = None,
        actor=None,
        audit_context: str | None = None,
    ) -> TreatmentStatus:
        """
        Every treatment-status write goes through here, which is what makes
        one audit call cover them all — the direct route, the episode-open
        and episode-close cascades, and ContactService's RPP cascade.
        """
        previous = self.statuses.get_current(patient_id)
        transition = self.statuses.create(
            TreatmentStatus(
                patient_id=patient_id,
                episode_id=episode_id,
                status=status,
                status_changed_date=status_changed_date,
                # changed_by is free text and predates the audit log; the
                # authenticated actor is recorded on the audit entry, which
                # is the trail a reviewer should read.
                changed_by=changed_by or (actor.name if actor else None),
                notes=notes,
            )
        )
        self.audit.record(
            action=AuditAction.STATUS_CHANGED,
            entity_type="treatment_status",
            entity_id=transition.treatment_status_id,
            patient_id=patient_id,
            actor=actor,
            field="status",
            old_value=previous.status if previous else None,
            new_value=status,
            context=audit_context,
        )
        return transition

    def get_current_status(self, patient_id: int) -> TreatmentStatus | None:
        return self.statuses.get_current(patient_id)
