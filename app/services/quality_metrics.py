"""
CoCM Quality Metrics report.

Tracks the same rate metrics as Caseload Statistics, but monthly across a
rolling 12-month window, per CLAUDE.md's Reporting Requirements. Nine rates
are named there; this module builds five of them for real and documents why
the other four can't be computed correctly yet rather than inventing them.

Caseload Reach (enrolled patients ÷ eligible population) is not computable
with this data model at all — the registry only has patients who are
already enrolled, with nothing representing "eligible but not yet
enrolled." Every row's caseload_reach field is None for exactly that
reason. Don't wire a fabricated denominator in later just to fill it; the
user's own literature research (Hahn et al. 2025; Kim et al. 2026
Psychiatric Services; Carroll et al. 2026 Psychiatric Services; Blackmore
et al. 2022 Psychiatric Services) confirms AIMS's exact eligible-population
methodology isn't published, so there's nothing safe to fall back on
either.

PTSD Improvement (PCL-5), Pediatric Anxiety Improvement (SCARED), Pediatric
Depression Response (SMFQ), and Pediatric ADHD Improvement (Vanderbilt) all
depend on clinical thresholds nobody has confirmed yet (see
app/services/scoring.py and CLAUDE.md's Symptom Score section).
assess_score() already returns is_response=False unconditionally for these
four measure types, so their rates always compute as 0/denominator here —
a correct conservative default, not a bug to "fix" without AIMS sign-off.

Engagement uses the definition supplied from the same literature research
above: a patient on the caseload during a month is "engaged" if they have
at least one completed (non-attempt) Contact with their care manager
during that month.

Measures Completion and Psychiatric Case Review rate have no equivalent
external citation on file. They're built as the most direct extension of
concepts the registry already tracks — a completed validated scale on a
Contact; a recorded Consultation — scoped to "at least one during the
month," mirroring Engagement's shape. Flagging this explicitly rather than
presenting it as a confirmed AIMS/NCQA definition: revisit if AIMS training
materials specify something different.

Depression Response and Anxiety Improvement here are the monthly, rolling
version of the same PHQ-9/GAD-7 response definitions used everywhere else
in this codebase (via assess_score) — distinct from the DRR Report's own
windowed version (see app/services/drr.py), which uses HEDIS's 4-6 month
follow-up window from baseline rather than a monthly snapshot.

"On caseload during a month" means the patient has an EpisodeOfCare open
at some point during that calendar month — the historical generalization
of "currently open episode," the same framing Caseload Statistics uses for
"right now" (see EpisodeRepository.list_open_during).
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import ContactType, MeasureType
from app.repositories.consultation import ConsultationRepository
from app.repositories.contact import ContactRepository
from app.repositories.episode import EpisodeRepository
from app.repositories.symptom_score import SymptomScoreRepository
from app.services.date_utils import month_bounds, shift_month
from app.services.scoring import (
    MEASURE_TO_CONDITION,
    ScoreRecord,
    assess_score,
    resolve_condition_measure,
)

# Measure types whose response/improvement rate this report tracks, and the
# QualityMetricsMonth field-name prefix each one accumulates into. Kept as
# one table rather than a chain of if/elif blocks per CLAUDE.md's "don't
# hardcode... in more than one place" rule.
_OUTCOME_MEASURES = {
    MeasureType.PHQ9: "depression_response",
    MeasureType.GAD7: "anxiety_improvement",
    MeasureType.PCL5: "ptsd_improvement",
    MeasureType.SCARED: "pediatric_anxiety_improvement",
    MeasureType.SMFQ: "pediatric_depression_response",
    MeasureType.VANDERBILT: "pediatric_adhd_improvement",
}


def _percentage(count: int, denominator: int) -> float:
    return round(100 * count / denominator, 1) if denominator else 0.0


@dataclass
class QualityMetricsMonth:
    year: int
    month: int  # 1-12

    caseload_size: int
    caseload_reach: float | None  # not computable — see module docstring

    engagement_count: int
    engagement_denominator: int
    engagement_percentage: float

    measures_completion_count: int
    measures_completion_denominator: int
    measures_completion_percentage: float

    depression_response_count: int
    depression_response_denominator: int
    depression_response_percentage: float

    anxiety_improvement_count: int
    anxiety_improvement_denominator: int
    anxiety_improvement_percentage: float

    ptsd_improvement_count: int
    ptsd_improvement_denominator: int
    ptsd_improvement_percentage: float

    pediatric_anxiety_improvement_count: int
    pediatric_anxiety_improvement_denominator: int
    pediatric_anxiety_improvement_percentage: float

    pediatric_depression_response_count: int
    pediatric_depression_response_denominator: int
    pediatric_depression_response_percentage: float

    pediatric_adhd_improvement_count: int
    pediatric_adhd_improvement_denominator: int
    pediatric_adhd_improvement_percentage: float

    psychiatric_case_review_count: int
    psychiatric_case_review_denominator: int
    psychiatric_case_review_percentage: float


def _build_month(db: Session, year: int, month: int) -> QualityMetricsMonth:
    start, end = month_bounds(year, month)

    episodes_this_month = EpisodeRepository(db).list_open_during(start, end)
    # One overlapping episode per patient is the normal case; if more than
    # one somehow overlaps the same month, keep the first found rather than
    # double-counting the patient in outcome denominators below.
    episode_by_patient = {}
    for episode in episodes_this_month:
        episode_by_patient.setdefault(episode.patient_id, episode)
    patient_ids = sorted(episode_by_patient.keys())
    caseload_size = len(patient_ids)

    contacts_repo = ContactRepository(db)
    scores_repo = SymptomScoreRepository(db)
    consultations_repo = ConsultationRepository(db)

    engaged = 0
    measures_completed = 0
    case_reviewed = 0
    outcome_counts = {suffix: 0 for suffix in _OUTCOME_MEASURES.values()}
    outcome_denominators = {suffix: 0 for suffix in _OUTCOME_MEASURES.values()}

    for patient_id in patient_ids:
        # Engagement means the patient was actually reached: attempts and
        # care-team-collaboration (about-the-patient, patient not present)
        # both fall outside it.
        month_contacts = [
            c
            for c in contacts_repo.list_by_patient(patient_id)
            if c.contact_type
            not in (ContactType.CONTACT_ATTEMPT, ContactType.CARE_TEAM_COLLABORATION)
            and start <= c.contact_date <= end
        ]
        if month_contacts:
            engaged += 1

        contact_ids_this_month = {c.contact_id for c in month_contacts}
        month_scores = [s for s in scores_repo.list_by_patient(patient_id) if start <= s.score_date <= end]
        if any(s.contact_id in contact_ids_this_month for s in month_scores):
            measures_completed += 1

        month_consultations = [
            c for c in consultations_repo.list_by_patient(patient_id) if start <= c.consultation_date <= end
        ]
        if month_consultations:
            case_reviewed += 1

        # Primary-diagnosis-driven (2026-08 design): the outcome a patient
        # counts toward is the measure mapped to their episode's primary
        # diagnosis, compared against that measure's own first score in
        # the episode; legacy episodes without a diagnosis fall back to
        # the condition their baseline measure implies.
        episode = episode_by_patient[patient_id]
        condition = episode.primary_diagnosis
        if condition is None and episode.baseline_measure_type is not None:
            condition = MEASURE_TO_CONDITION.get(episode.baseline_measure_type)
        if condition is None:
            continue

        scores_to_date = [
            s for s in scores_repo.list_by_episode(episode.episode_id) if s.score_date <= end
        ]
        measure_type = resolve_condition_measure(
            condition,
            baseline_measure_type=episode.baseline_measure_type,
            measures_with_scores={s.measure_type for s in scores_to_date},
        )
        if measure_type is None or measure_type not in _OUTCOME_MEASURES:
            continue

        same_measure_to_date = sorted(
            (s for s in scores_to_date if s.measure_type == measure_type),
            key=lambda s: (s.score_date, s.score_id),
        )
        if len(same_measure_to_date) < 2:
            continue  # only a baseline on file so far — nothing to compare it against yet
        first, latest = same_measure_to_date[0], same_measure_to_date[-1]

        assessment = assess_score(
            ScoreRecord(measure_type, first.score_value, first.score_date),
            ScoreRecord(measure_type, latest.score_value, latest.score_date),
        )
        suffix = _OUTCOME_MEASURES[measure_type]
        outcome_denominators[suffix] += 1
        outcome_counts[suffix] += int(assessment.is_response)

    return QualityMetricsMonth(
        year=year,
        month=month,
        caseload_size=caseload_size,
        caseload_reach=None,
        engagement_count=engaged,
        engagement_denominator=caseload_size,
        engagement_percentage=_percentage(engaged, caseload_size),
        measures_completion_count=measures_completed,
        measures_completion_denominator=caseload_size,
        measures_completion_percentage=_percentage(measures_completed, caseload_size),
        depression_response_count=outcome_counts["depression_response"],
        depression_response_denominator=outcome_denominators["depression_response"],
        depression_response_percentage=_percentage(
            outcome_counts["depression_response"], outcome_denominators["depression_response"]
        ),
        anxiety_improvement_count=outcome_counts["anxiety_improvement"],
        anxiety_improvement_denominator=outcome_denominators["anxiety_improvement"],
        anxiety_improvement_percentage=_percentage(
            outcome_counts["anxiety_improvement"], outcome_denominators["anxiety_improvement"]
        ),
        ptsd_improvement_count=outcome_counts["ptsd_improvement"],
        ptsd_improvement_denominator=outcome_denominators["ptsd_improvement"],
        ptsd_improvement_percentage=_percentage(
            outcome_counts["ptsd_improvement"], outcome_denominators["ptsd_improvement"]
        ),
        pediatric_anxiety_improvement_count=outcome_counts["pediatric_anxiety_improvement"],
        pediatric_anxiety_improvement_denominator=outcome_denominators["pediatric_anxiety_improvement"],
        pediatric_anxiety_improvement_percentage=_percentage(
            outcome_counts["pediatric_anxiety_improvement"], outcome_denominators["pediatric_anxiety_improvement"]
        ),
        pediatric_depression_response_count=outcome_counts["pediatric_depression_response"],
        pediatric_depression_response_denominator=outcome_denominators["pediatric_depression_response"],
        pediatric_depression_response_percentage=_percentage(
            outcome_counts["pediatric_depression_response"], outcome_denominators["pediatric_depression_response"]
        ),
        pediatric_adhd_improvement_count=outcome_counts["pediatric_adhd_improvement"],
        pediatric_adhd_improvement_denominator=outcome_denominators["pediatric_adhd_improvement"],
        pediatric_adhd_improvement_percentage=_percentage(
            outcome_counts["pediatric_adhd_improvement"], outcome_denominators["pediatric_adhd_improvement"]
        ),
        psychiatric_case_review_count=case_reviewed,
        psychiatric_case_review_denominator=caseload_size,
        psychiatric_case_review_percentage=_percentage(case_reviewed, caseload_size),
    )


def build_quality_metrics(db: Session, as_of: date) -> list[QualityMetricsMonth]:
    """
    Twelve rows, oldest to newest, ending with the calendar month
    containing as_of — the rolling 12-month window CLAUDE.md describes.
    """
    return [_build_month(db, *shift_month(as_of.year, as_of.month, delta)) for delta in range(-11, 1)]
