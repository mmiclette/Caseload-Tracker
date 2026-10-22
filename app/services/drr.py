"""
DRR (Depression Remission or Response) Report.

Built from the HEDIS spec details the user supplied directly (not
invented, per CLAUDE.md's "don't invent it, flag it" discipline):

  Depression Response: 50% or greater reduction in PHQ-9 from baseline.
  Depression Remission: a PHQ-9 score of less than 5.
  Follow-up window: 4-8 months after the baseline (index) measure.
  Corrected from 4-6 to 4-8 on 2026-08-07: the CTMS's own Follow-Up PHQ-9
  tooltip states "a PHQ-9 score documented at 4-8 months after the initial
  elevated score," and Matt confirmed 4-8 is authoritative
  (docs/ctms-reference/README.md).

This module still has to make a few structural calls the user didn't
spell out, each flagged here rather than presented as confirmed HEDIS
methodology:

  - Denominator convention: all three rates (Follow-Up PHQ-9 completion,
    Depression Remission, Depression Response) use the full eligible
    cohort as their denominator, not just the patients who completed a
    follow-up assessment. This matches how real HEDIS DRR measures work —
    a patient who never gets a follow-up PHQ-9 counts as a remission/
    response failure, rather than being excluded — which is what gives
    the "Follow-Up PHQ-9" completion metric its own teeth as a distinct
    number worth watching. If AIMS's actual implementation scores this
    differently, this is the one place to change it.
  - Eligible cohort: index episodes are episodes whose baseline
    measure_type is PHQ9 and whose baseline_date falls in the report
    year. An episode is only included once its 4-8 month follow-up window
    has fully closed as of `as_of` — otherwise whether it will complete a
    follow-up is genuinely still unknown, and forcing it into the
    denominator early would understate the rates for no good reason.
    Practical effect: a DRR report run for the current year, close to
    today, is necessarily incomplete for episodes with recent baselines —
    this is expected, not a bug.
  - Clinic attribution: grouped by each patient's current clinic
    assignment (their primary one if they have more than one), the same
    "current clinic" framing Caseload Statistics uses for its own
    group_by="clinic" mode. A patient with no current clinic assignment
    groups under "unassigned" rather than being dropped from the report.
  - If more than one PHQ-9 score falls inside the follow-up window, the
    most recent one is used as "the" follow-up score, consistent with how
    every other report in this codebase picks a single score per measure
    type when more than one exists.
"""

import calendar
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import MeasureType
from app.repositories.clinic_assignment import ClinicAssignmentRepository
from app.repositories.episode import EpisodeRepository
from app.repositories.symptom_score import SymptomScoreRepository
from app.services.scoring import PHQ9_REMISSION_THRESHOLD, ScoreRecord, assess_score

FOLLOW_UP_WINDOW_START_MONTHS = 4
FOLLOW_UP_WINDOW_END_MONTHS = 8
UNASSIGNED_CLINIC_KEY = "unassigned"


def _add_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _percentage(count: int, denominator: int) -> float:
    return round(100 * count / denominator, 1) if denominator else 0.0


def _clinic_key_for_patient(db: Session, patient_id: int) -> str:
    assignments = ClinicAssignmentRepository(db).list_current_by_patient(patient_id)
    if not assignments:
        return UNASSIGNED_CLINIC_KEY
    primary = next((a for a in assignments if a.is_primary), None)
    return (primary or assignments[0]).clinic_id


@dataclass
class DRRClinicRow:
    clinic_id: str
    index_episode_count: int  # the eligible cohort size — every rate's denominator

    follow_up_phq9_count: int
    follow_up_phq9_percentage: float

    depression_remission_count: int
    depression_remission_percentage: float

    depression_response_count: int
    depression_response_percentage: float


def build_drr_report(db: Session, year: int, as_of: date | None = None) -> list[DRRClinicRow]:
    as_of = as_of or date.today()
    episodes_repo = EpisodeRepository(db)
    scores_repo = SymptomScoreRepository(db)

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    cohort = [
        e
        for e in episodes_repo.list_open_during(year_start, year_end)
        if e.baseline_measure_type == MeasureType.PHQ9 and year_start <= e.baseline_date <= year_end
    ]

    totals: dict[str, dict] = {}

    for episode in cohort:
        window_start = _add_months(episode.baseline_date, FOLLOW_UP_WINDOW_START_MONTHS)
        window_end = _add_months(episode.baseline_date, FOLLOW_UP_WINDOW_END_MONTHS)
        if as_of < window_end:
            continue  # window hasn't closed yet — outcome unknown, not a failure

        clinic_key = _clinic_key_for_patient(db, episode.patient_id)
        row = totals.setdefault(
            clinic_key,
            {"index_episode_count": 0, "follow_up_phq9_count": 0, "remission_count": 0, "response_count": 0},
        )
        row["index_episode_count"] += 1

        window_scores = [
            s
            for s in scores_repo.list_by_episode(episode.episode_id)
            if s.measure_type == MeasureType.PHQ9 and window_start <= s.score_date <= window_end
        ]
        if not window_scores:
            continue  # no follow-up PHQ-9 completed — counts against every rate, per module docstring

        row["follow_up_phq9_count"] += 1
        follow_up = max(window_scores, key=lambda s: s.score_date)

        if follow_up.score_value < PHQ9_REMISSION_THRESHOLD:
            row["remission_count"] += 1

        assessment = assess_score(
            ScoreRecord(MeasureType.PHQ9, episode.baseline_score, episode.baseline_date),
            ScoreRecord(MeasureType.PHQ9, follow_up.score_value, follow_up.score_date),
        )
        if assessment.is_response:
            row["response_count"] += 1

    return [
        DRRClinicRow(
            clinic_id=clinic_key,
            index_episode_count=totals_row["index_episode_count"],
            follow_up_phq9_count=totals_row["follow_up_phq9_count"],
            follow_up_phq9_percentage=_percentage(
                totals_row["follow_up_phq9_count"], totals_row["index_episode_count"]
            ),
            depression_remission_count=totals_row["remission_count"],
            depression_remission_percentage=_percentage(
                totals_row["remission_count"], totals_row["index_episode_count"]
            ),
            depression_response_count=totals_row["response_count"],
            depression_response_percentage=_percentage(
                totals_row["response_count"], totals_row["index_episode_count"]
            ),
        )
        for clinic_key, totals_row in sorted(totals.items())
    ]
