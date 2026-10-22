from datetime import date, timedelta

import pytest

from app.models.enums import MeasureType
from app.services.scoring import (
    ScoreRecord,
    assess_score,
    determine_baseline,
    is_new_episode_gap,
    phq9_score_color,
)


def score(measure_type, value, day_offset):
    return ScoreRecord(
        measure_type=measure_type,
        score_value=value,
        score_date=date(2026, 1, 1) + timedelta(days=day_offset),
    )


class TestDetermineBaseline:
    def test_empty_list_returns_none(self):
        assert determine_baseline([]) is None

    def test_single_score_is_baseline(self):
        s = score(MeasureType.PHQ9, 15, 1)
        assert determine_baseline([s]) == s

    def test_earliest_score_wins_regardless_of_order(self):
        early = score(MeasureType.PHQ9, 20, 3)
        late = score(MeasureType.PHQ9, 10, 20)
        assert determine_baseline([late, early]) == early


class TestNewEpisodeGap:
    def test_gap_under_six_months_is_not_new_episode(self):
        assert is_new_episode_gap(date(2026, 1, 1), date(2026, 5, 1)) is False

    def test_gap_of_exactly_182_days_is_new_episode(self):
        end = date(2026, 1, 1)
        returned = date(2026, 7, 2)  # 182 days later
        assert (returned - end).days == 182
        assert is_new_episode_gap(end, returned) is True

    def test_gap_over_six_months_is_new_episode(self):
        assert is_new_episode_gap(date(2026, 1, 1), date(2027, 1, 1)) is True


class TestPHQ9Assessment:
    def test_remission_when_score_under_five(self):
        baseline = score(MeasureType.PHQ9, 18, 1)
        current = score(MeasureType.PHQ9, 4, 60)
        result = assess_score(baseline, current)
        assert result.is_remission is True

    def test_no_remission_at_score_of_five(self):
        baseline = score(MeasureType.PHQ9, 18, 1)
        current = score(MeasureType.PHQ9, 5, 60)
        result = assess_score(baseline, current)
        assert result.is_remission is False

    def test_response_at_exactly_fifty_percent_improvement(self):
        baseline = score(MeasureType.PHQ9, 20, 1)
        current = score(MeasureType.PHQ9, 10, 60)  # exactly 50% improvement
        result = assess_score(baseline, current)
        assert result.is_response is True
        assert result.percent_improvement == 0.5

    def test_no_response_below_fifty_percent_improvement(self):
        baseline = score(MeasureType.PHQ9, 20, 1)
        current = score(MeasureType.PHQ9, 11, 60)  # 45% improvement
        result = assess_score(baseline, current)
        assert result.is_response is False

    def test_worsening_score_yields_negative_improvement_and_no_response(self):
        baseline = score(MeasureType.PHQ9, 10, 1)
        current = score(MeasureType.PHQ9, 15, 60)
        result = assess_score(baseline, current)
        assert result.point_improvement == -5
        assert result.is_response is False
        assert result.is_remission is False

    def test_zero_baseline_gives_undefined_percent_improvement(self):
        baseline = score(MeasureType.PHQ9, 0, 1)
        current = score(MeasureType.PHQ9, 0, 60)
        result = assess_score(baseline, current)
        assert result.percent_improvement is None
        assert result.is_response is False


class TestGAD7Assessment:
    def test_response_at_exactly_five_point_improvement(self):
        baseline = score(MeasureType.GAD7, 15, 1)
        current = score(MeasureType.GAD7, 10, 60)
        result = assess_score(baseline, current)
        assert result.is_response is True
        assert result.point_improvement == 5

    def test_no_response_below_five_point_improvement(self):
        baseline = score(MeasureType.GAD7, 15, 1)
        current = score(MeasureType.GAD7, 11, 60)
        result = assess_score(baseline, current)
        assert result.is_response is False

    def test_gad7_remission_below_five(self):
        """GAD-7 remission is a score under 5 — confirmed by Matt 2026-08-07."""
        baseline = score(MeasureType.GAD7, 15, 1)
        current = score(MeasureType.GAD7, 1, 60)
        result = assess_score(baseline, current)
        assert result.is_remission is True

    def test_gad7_no_remission_at_five(self):
        baseline = score(MeasureType.GAD7, 15, 1)
        current = score(MeasureType.GAD7, 5, 60)
        result = assess_score(baseline, current)
        assert result.is_remission is False


class TestPHQ9ScoreColor:
    """
    The CTMS caseload list's Last PHQ-9 traffic light, confirmed from its
    own tooltip (docs/ctms-reference/README.md): red = >=10 and not 50%
    improved; yellow = 5-9 OR 50%+ improved; green = <=4.
    """

    def test_green_at_four_or_below(self):
        assert phq9_score_color(18, 4) == "green"
        assert phq9_score_color(18, 0) == "green"

    def test_yellow_moderate_band(self):
        assert phq9_score_color(8, 7) == "yellow"
        assert phq9_score_color(8, 5) == "yellow"
        assert phq9_score_color(8, 9) == "yellow"

    def test_red_elevated_without_response(self):
        assert phq9_score_color(14, 14) == "red"
        assert phq9_score_color(18, 10) == "red"  # 44% improvement isn't 50%

    def test_yellow_elevated_but_fifty_percent_improved(self):
        assert phq9_score_color(20, 10) == "yellow"
        assert phq9_score_color(24, 12) == "yellow"

    def test_zero_baseline_cannot_claim_improvement(self):
        assert phq9_score_color(0, 12) == "red"


class TestCrossMeasureGuard:
    def test_mismatched_measure_types_raise(self):
        baseline = score(MeasureType.PHQ9, 18, 1)
        current = score(MeasureType.GAD7, 5, 60)
        with pytest.raises(ValueError):
            assess_score(baseline, current)


class TestUnscoredMeasuresStayConservative:
    """
    PCL-5 (PTSD), SCARED (pediatric anxiety), SMFQ (pediatric depression),
    and Vanderbilt (pediatric ADHD) are tracked by the CTMS, but no source
    material has stated their numeric remission/response thresholds yet.
    These tests lock in the deliberate choice not to guess: any measure
    type without a defined rule reports no remission and no response,
    rather than silently reusing PHQ-9 or GAD-7 math on scales it was
    never validated for.
    """

    @pytest.mark.parametrize(
        "measure_type",
        [MeasureType.PCL5, MeasureType.SCARED, MeasureType.SMFQ, MeasureType.VANDERBILT],
    )
    def test_large_improvement_on_unscored_measure_is_not_flagged(self, measure_type):
        baseline = score(measure_type, 40, 1)
        current = score(measure_type, 2, 60)  # a dramatic improvement either way
        result = assess_score(baseline, current)
        assert result.is_remission is False
        assert result.is_response is False
        # We still report the raw math — only the remission/response
        # *interpretation* of it is withheld.
        assert result.point_improvement == 38
