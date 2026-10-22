"""
Baseline, remission, and response calculations.

This module is the single source of truth for every clinical threshold used
across the registry. Nothing outside this file should hardcode a
remission/response number — reporting, routes, and reminders all import
from here. If a threshold changes, it changes in exactly one place.

Thresholds (per CLAUDE.md / AIMS Center guidance):
  - PHQ-9 remission: score < 5
  - PHQ-9 / depression response: >= 50% improvement from the episode baseline
  - GAD-7 remission: score < 5 (confirmed by Matt 2026-08-07 — remission is
    not PHQ-9-only)
  - GAD-7 anxiety improvement/response: >= 5-point improvement from the
    episode baseline
  - New episode vs. continued episode: a gap of >= 6 months (182 days) between
    the end of one episode and a patient's return to treatment starts a new
    episode with a new baseline, rather than continuing the old one.

This module also owns the condition -> measure mapping (CONDITION_MEASURES)
introduced with Episode primary/secondary diagnoses: which validated
measure tracks each treated condition, and therefore which measure a
patient's primary diagnosis pins their caseload response/remission
metrics to. One table, imported everywhere — never duplicated.
"""

from dataclasses import dataclass
from datetime import date

from app.models.enums import ConditionType, MeasureType

PHQ9_REMISSION_THRESHOLD = 5  # remission if score is strictly below this
PHQ9_RESPONSE_FRACTION = 0.5  # 50% improvement from baseline counts as response
GAD7_REMISSION_THRESHOLD = 5  # remission if score is strictly below this
GAD7_RESPONSE_POINT_IMPROVEMENT = 5  # absolute point improvement from baseline
NEW_EPISODE_GAP_DAYS = 182  # ~6 months; a gap this long or longer starts a new episode

# Caseload-list score-cell indicators, confirmed from the CTMS's own
# column tooltips (docs/ctms-reference/README.md, Matt-supplied
# screenshots): an asterisk marks a score more than 30 days old (needs
# re-administration), and the Last PHQ-9 cell is colored red (>= 10 and
# not 50% improved from baseline), yellow (5-9, or 50%+ improved), or
# green (<= 4). Only PHQ-9's color rules are confirmed — do not invent
# GAD-7/PCL-5 analogs.
SCORE_STALE_DAYS = 30
PHQ9_ELEVATED_THRESHOLD = 10  # red band starts here (absent 50% improvement)
PHQ9_GREEN_MAX = 4  # green band: most recent score is 4 or below


def phq9_score_color(baseline_value: int, latest_value: int) -> str:
    """
    The CTMS's Last PHQ-9 traffic light: "red" / "yellow" / "green" per
    the confirmed rules above. Green is checked first (most specific),
    then the yellow escape hatches (moderate band, or 50%+ improved), and
    what remains — >= 10 without a 50% improvement — is red.
    """
    if latest_value <= PHQ9_GREEN_MAX:
        return "green"
    improvement = (baseline_value - latest_value) / baseline_value if baseline_value else 0.0
    if latest_value < PHQ9_ELEVATED_THRESHOLD or improvement >= PHQ9_RESPONSE_FRACTION:
        return "yellow"
    return "red"

# Which measures can track each treated condition, adult listed before
# pediatric — the episode's actual scores (or its baseline measure)
# disambiguate. SUBSTANCE_USE is empty until AUDIT-C/DAST-10 become
# MeasureTypes (patient-profile Bucket A).
CONDITION_MEASURES: dict[ConditionType, list[MeasureType]] = {
    ConditionType.DEPRESSION: [MeasureType.PHQ9, MeasureType.SMFQ],
    ConditionType.ANXIETY: [MeasureType.GAD7, MeasureType.SCARED],
    ConditionType.PTSD: [MeasureType.PCL5],
    ConditionType.ADHD: [MeasureType.VANDERBILT],
    ConditionType.SUBSTANCE_USE: [],
}

# Reverse map, used as the legacy fallback: an episode recorded before
# primary_diagnosis existed still reports under the condition its baseline
# measure implies. MeasureType.OTHER maps to no condition.
MEASURE_TO_CONDITION: dict[MeasureType, ConditionType] = {
    measure: condition
    for condition, measures in CONDITION_MEASURES.items()
    for measure in measures
}


def resolve_condition_measure(
    condition: ConditionType,
    *,
    baseline_measure_type: MeasureType | None,
    measures_with_scores: set[MeasureType],
) -> MeasureType | None:
    """
    Which concrete measure tracks `condition` for a given episode: the
    episode's baseline measure if it's one of the condition's candidates,
    else the first candidate that actually has scores in the episode, else
    the condition's first (adult) candidate — or None for a condition with
    no mapped measures (substance_use, for now).
    """
    candidates = CONDITION_MEASURES[condition]
    if not candidates:
        return None
    if baseline_measure_type in candidates:
        return baseline_measure_type
    for candidate in candidates:
        if candidate in measures_with_scores:
            return candidate
    return candidates[0]


@dataclass(frozen=True)
class ScoreRecord:
    """Minimal shape the scoring functions need from a SymptomScore row."""

    measure_type: MeasureType
    score_value: int
    score_date: date


@dataclass(frozen=True)
class ScoreAssessment:
    """Result of comparing a score against an episode baseline."""

    is_remission: bool
    is_response: bool
    percent_improvement: float | None  # None if baseline is 0 (undefined % improvement)
    point_improvement: int


def determine_baseline(scores: list[ScoreRecord]) -> ScoreRecord | None:
    """
    The baseline is the first validated score recorded in an episode,
    i.e. the score with the earliest score_date. Ties on score_date are
    broken by input order (assume caller passes scores in the order they
    were recorded if score_date collides).
    """
    if not scores:
        return None
    return min(scores, key=lambda s: s.score_date)


def is_new_episode_gap(previous_episode_end_date: date, return_date: date) -> bool:
    """
    True if the gap between a patient's prior episode ending and their
    return to treatment is 6 months (182 days) or more, meaning a new
    episode (with a new baseline) should be started rather than reopening
    the old one.
    """
    return (return_date - previous_episode_end_date).days >= NEW_EPISODE_GAP_DAYS


def assess_score(baseline: ScoreRecord, current: ScoreRecord) -> ScoreAssessment:
    """
    Compare a current score against the episode baseline and report
    remission/response status. baseline and current must be the same
    measure_type — comparing a PHQ-9 baseline against a GAD-7 follow-up
    score (or vice versa) is a caller error.
    """
    if baseline.measure_type != current.measure_type:
        raise ValueError(
            "Cannot compare scores of different measure types: "
            f"baseline={baseline.measure_type} current={current.measure_type}"
        )

    point_improvement = baseline.score_value - current.score_value
    percent_improvement = (
        point_improvement / baseline.score_value if baseline.score_value else None
    )

    if current.measure_type == MeasureType.PHQ9:
        is_remission = current.score_value < PHQ9_REMISSION_THRESHOLD
        is_response = (
            percent_improvement is not None
            and percent_improvement >= PHQ9_RESPONSE_FRACTION
        )
    elif current.measure_type == MeasureType.GAD7:
        is_remission = current.score_value < GAD7_REMISSION_THRESHOLD
        is_response = point_improvement >= GAD7_RESPONSE_POINT_IMPROVEMENT
    else:
        is_remission = False
        is_response = False

    return ScoreAssessment(
        is_remission=is_remission,
        is_response=is_response,
        percent_improvement=percent_improvement,
        point_improvement=point_improvement,
    )
