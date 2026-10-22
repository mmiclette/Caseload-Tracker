"""
Episode primary/secondary diagnosis, the condition -> measure mapping, and
everything downstream of it: the soft baseline-consistency rule, the
primary-driven caseload outcome rates, and the Clinical Dashboard's
measure trend graphs.
"""

from datetime import date

import pytest

from app.models.care_team_assignment import CareTeamAssignment
from app.models.enums import (
    CareTeamRole,
    ConditionType,
    ContactType,
    MeasureType,
    ProviderRole,
)
from app.models.patient import Patient
from app.models.provider import Provider
from app.repositories.care_team_assignment import CareTeamAssignmentRepository
from app.repositories.patient import PatientRepository
from app.repositories.provider import ProviderRepository
from app.services.contact_service import ContactService
from app.services.episode_service import EpisodeService
from app.services.reporting import build_caseload_statistics, build_clinical_dashboard
from app.services.scoring import resolve_condition_measure


def make_patient(db_session, mrn):
    return PatientRepository(db_session).create(
        Patient(
            mrn=mrn,
            name="Diagnosis Test Patient",
            payer="Medicaid",
            date_of_birth=date(1985, 3, 20),
            consent_date=date(2026, 1, 1),
            enrollment_date=date(2026, 1, 1),
        )
    )


def record_scores(db_session, patient_id, episode_id, contact_date, scores, contact_type=ContactType.FOLLOW_UP):
    ContactService(db_session).record_contact(
        patient_id=patient_id,
        episode_id=episode_id,
        contact_type=contact_type,
        contact_date=contact_date,
        duration_minutes=30,
        scores=scores,
    )


# --- validation ---------------------------------------------------------------


def test_secondary_must_differ_from_primary(db_session):
    patient = make_patient(db_session, "MRN-DX-1")
    with pytest.raises(ValueError, match="must differ"):
        EpisodeService(db_session).create_episode(
            patient_id=patient.patient_id,
            start_date=date(2026, 1, 1),
            primary_diagnosis=ConditionType.ANXIETY,
            secondary_diagnosis=ConditionType.ANXIETY,
        )


def test_secondary_requires_primary(db_session):
    patient = make_patient(db_session, "MRN-DX-2")
    with pytest.raises(ValueError, match="requires a primary"):
        EpisodeService(db_session).create_episode(
            patient_id=patient.patient_id,
            start_date=date(2026, 1, 1),
            secondary_diagnosis=ConditionType.ANXIETY,
        )


def test_update_validates_merged_diagnoses(db_session):
    patient = make_patient(db_session, "MRN-DX-3")
    service = EpisodeService(db_session)
    episode = service.create_episode(
        patient_id=patient.patient_id,
        start_date=date(2026, 1, 1),
        primary_diagnosis=ConditionType.DEPRESSION,
    )
    with pytest.raises(ValueError, match="must differ"):
        service.update_episode(episode.episode_id, secondary_diagnosis=ConditionType.DEPRESSION)


# --- condition -> measure resolution -------------------------------------------


def test_resolution_prefers_baseline_then_scores_then_adult_default():
    assert (
        resolve_condition_measure(
            ConditionType.DEPRESSION,
            baseline_measure_type=MeasureType.SMFQ,
            measures_with_scores={MeasureType.PHQ9, MeasureType.SMFQ},
        )
        == MeasureType.SMFQ  # baseline wins when it's a candidate
    )
    assert (
        resolve_condition_measure(
            ConditionType.ANXIETY,
            baseline_measure_type=MeasureType.PHQ9,
            measures_with_scores={MeasureType.SCARED},
        )
        == MeasureType.SCARED  # else first candidate with scores
    )
    assert (
        resolve_condition_measure(
            ConditionType.ANXIETY,
            baseline_measure_type=None,
            measures_with_scores=set(),
        )
        == MeasureType.GAD7  # else the adult default
    )
    assert (
        resolve_condition_measure(
            ConditionType.SUBSTANCE_USE,
            baseline_measure_type=None,
            measures_with_scores=set(),
        )
        is None  # no mapped measures until AUDIT-C/DAST-10 exist
    )


# --- soft baseline consistency --------------------------------------------------


def test_baseline_reanchors_onto_primary_mapped_measure(db_session):
    """
    Primary is anxiety, but a PHQ-9 lands first: the PHQ-9 initially
    becomes the baseline, then the first GAD-7 re-anchors it (a
    primary-mapped measure beats a non-mapped one).
    """
    patient = make_patient(db_session, "MRN-DX-4")
    service = EpisodeService(db_session)
    episode = service.create_episode(
        patient_id=patient.patient_id,
        start_date=date(2026, 1, 1),
        primary_diagnosis=ConditionType.ANXIETY,
    )
    record_scores(
        db_session, patient.patient_id, episode.episode_id, date(2026, 1, 2),
        [{"measure_type": MeasureType.PHQ9, "score_value": 14}],
        contact_type=ContactType.INITIAL_ASSESSMENT,
    )
    db_session.refresh(episode)
    assert episode.baseline_measure_type == MeasureType.PHQ9  # only score so far

    record_scores(
        db_session, patient.patient_id, episode.episode_id, date(2026, 1, 16),
        [{"measure_type": MeasureType.GAD7, "score_value": 16}],
    )
    db_session.refresh(episode)
    assert episode.baseline_measure_type == MeasureType.GAD7
    assert episode.baseline_score == 16
    assert episode.baseline_date == date(2026, 1, 16)


def test_baseline_unchanged_without_primary_diagnosis(db_session):
    """Legacy behavior preserved: first measure recorded keeps the baseline."""
    patient = make_patient(db_session, "MRN-DX-5")
    service = EpisodeService(db_session)
    episode = service.create_episode(patient_id=patient.patient_id, start_date=date(2026, 1, 1))
    record_scores(
        db_session, patient.patient_id, episode.episode_id, date(2026, 1, 2),
        [{"measure_type": MeasureType.PHQ9, "score_value": 14}],
        contact_type=ContactType.INITIAL_ASSESSMENT,
    )
    record_scores(
        db_session, patient.patient_id, episode.episode_id, date(2026, 1, 16),
        [{"measure_type": MeasureType.GAD7, "score_value": 16}],
    )
    db_session.refresh(episode)
    assert episode.baseline_measure_type == MeasureType.PHQ9


# --- primary-driven caseload rates ----------------------------------------------


def test_anxiety_primary_tracks_gad7_not_phq9(db_session):
    """
    A dual-scale patient with primary anxiety counts toward the anxiety
    rates via GAD-7 — their PHQ-9 series doesn't put them in the
    depression bucket.
    """
    provider = ProviderRepository(db_session).create(
        Provider(name="Dx CM", role=ProviderRole.CARE_MANAGER)
    )
    patient = make_patient(db_session, "MRN-DX-6")
    CareTeamAssignmentRepository(db_session).create(
        CareTeamAssignment(
            patient_id=patient.patient_id,
            provider_id=provider.provider_id,
            role=CareTeamRole.CARE_MANAGER,
            service_begin_date=date(2026, 1, 1),
        )
    )
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id,
        start_date=date(2026, 1, 1),
        primary_diagnosis=ConditionType.ANXIETY,
        secondary_diagnosis=ConditionType.DEPRESSION,
    )
    record_scores(
        db_session, patient.patient_id, episode.episode_id, date(2026, 1, 2),
        [
            {"measure_type": MeasureType.GAD7, "score_value": 16},
            {"measure_type": MeasureType.PHQ9, "score_value": 18},
        ],
        contact_type=ContactType.INITIAL_ASSESSMENT,
    )
    record_scores(
        db_session, patient.patient_id, episode.episode_id, date(2026, 2, 15),
        [
            {"measure_type": MeasureType.GAD7, "score_value": 4},   # response (12pt) + remission (<5)
            {"measure_type": MeasureType.PHQ9, "score_value": 3},   # would be response+remission, but not counted
        ],
    )

    rows = build_caseload_statistics(db_session, group_by="provider")
    row = next(r for r in rows if r.group_key == str(provider.provider_id))

    assert row.anxiety_response_denominator == 1
    assert row.anxiety_response_count == 1
    assert row.anxiety_remission_count == 1
    assert row.depression_response_denominator == 0
    assert row.depression_remission_denominator == 0


# --- dashboard measure trends ----------------------------------------------------


def test_two_diagnoses_two_trend_graphs(db_session):
    patient = make_patient(db_session, "MRN-DX-7")
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id,
        start_date=date(2026, 1, 1),
        primary_diagnosis=ConditionType.DEPRESSION,
        secondary_diagnosis=ConditionType.ANXIETY,
    )
    record_scores(
        db_session, patient.patient_id, episode.episode_id, date(2026, 1, 2),
        [
            {"measure_type": MeasureType.PHQ9, "score_value": 18},
            {"measure_type": MeasureType.GAD7, "score_value": 15},
        ],
        contact_type=ContactType.INITIAL_ASSESSMENT,
    )
    record_scores(
        db_session, patient.patient_id, episode.episode_id, date(2026, 2, 1),
        [
            {"measure_type": MeasureType.PHQ9, "score_value": 8},
            {"measure_type": MeasureType.GAD7, "score_value": 4},
        ],
    )

    dashboard = build_clinical_dashboard(db_session, patient.patient_id)
    assert len(dashboard.measure_trends) == 2

    primary = dashboard.measure_trends[0]
    assert primary.is_primary is True
    assert primary.condition == ConditionType.DEPRESSION
    assert primary.measure_type == MeasureType.PHQ9
    assert primary.baseline_score == 18
    assert primary.latest_score == 8
    assert primary.is_response is True   # 18 -> 8 is >= 50%
    assert primary.is_remission is False  # 8 is not < 5
    assert [p.score_value for p in primary.scores] == [18, 8]

    secondary = dashboard.measure_trends[1]
    assert secondary.is_primary is False
    assert secondary.condition == ConditionType.ANXIETY
    assert secondary.measure_type == MeasureType.GAD7
    assert secondary.is_response is True   # 15 -> 4 is an 11-point improvement
    assert secondary.is_remission is True  # 4 < 5


def test_legacy_episode_gets_trend_from_baseline_fallback(db_session):
    patient = make_patient(db_session, "MRN-DX-8")
    episode = EpisodeService(db_session).create_episode(
        patient_id=patient.patient_id, start_date=date(2026, 1, 1)
    )
    record_scores(
        db_session, patient.patient_id, episode.episode_id, date(2026, 1, 2),
        [{"measure_type": MeasureType.PHQ9, "score_value": 18}],
        contact_type=ContactType.INITIAL_ASSESSMENT,
    )

    dashboard = build_clinical_dashboard(db_session, patient.patient_id)
    assert len(dashboard.measure_trends) == 1
    trend = dashboard.measure_trends[0]
    assert trend.condition == ConditionType.DEPRESSION
    assert trend.is_primary is True
    assert trend.is_response is None  # single score — nothing to compare yet
    assert trend.is_remission is False  # 18 is not < 5


def test_patient_with_no_episodes_has_no_trends(db_session):
    patient = make_patient(db_session, "MRN-DX-9")
    dashboard = build_clinical_dashboard(db_session, patient.patient_id)
    assert dashboard.measure_trends == []
