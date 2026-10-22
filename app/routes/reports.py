from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_provider
from app.database import get_db
from app.core.config import settings
from app.schemas.reporting import (
    ActivePatientRowRead,
    CaseloadStatisticsRowRead,
    ClinicalDashboardRead,
    CompletedEpisodeStatisticsRead,
    DRRClinicRowRead,
    QualityMetricsMonthRead,
    TimeTrackerPatientRowRead,
)
from app.services.drr import build_drr_report
from app.services.quality_metrics import build_quality_metrics
from app.services.reporting import (
    build_active_patients_report,
    build_caseload_statistics,
    build_clinical_dashboard,
    build_completed_episode_statistics,
)
from app.services.time_tracker import build_monthly_time_tracker

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(get_current_provider)])


@router.get("/active-patients", response_model=list[ActivePatientRowRead])
def active_patients_report(
    payer: str | None = None,
    clinic_id: str | None = None,
    provider_id: int | None = None,
    as_of: date | None = None,
    db: Session = Depends(get_db),
):
    """
    The CTMS's "Active Patients" caseload report — see CLAUDE.md's
    Reporting Requirements for the confirmed column order. Filterable by
    payer, clinic, and provider so one Care Manager can cover another's
    caseload during leave.
    """
    return build_active_patients_report(
        db, payer=payer, clinic_id=clinic_id, provider_id=provider_id, as_of=as_of
    )


@router.get("/clinical-dashboard/{patient_id}", response_model=ClinicalDashboardRead)
def clinical_dashboard_report(patient_id: int, db: Session = Depends(get_db)):
    """The CTMS's per-patient Clinical Dashboard — see build_clinical_dashboard."""
    try:
        return build_clinical_dashboard(db, patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/caseload-statistics", response_model=list[CaseloadStatisticsRowRead])
def caseload_statistics_report(
    group_by: str = "provider", as_of: date | None = None, db: Session = Depends(get_db)
):
    """
    group_by="provider" (default) or "clinic" — see build_caseload_statistics.
    A per-Psychiatric-Consultant or per-PCP view is this same endpoint
    filtered client-side by group_label's role suffix, not a separate mode.
    as_of (default today) only anchors the "not improving and not reviewed
    in the past two months" window.
    """
    try:
        return build_caseload_statistics(db, group_by=group_by, as_of=as_of)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/completed-episode-statistics", response_model=CompletedEpisodeStatisticsRead)
def completed_episode_statistics_report(year: int, db: Session = Depends(get_db)):
    """
    Per-calendar-year cohort of every episode closed that year — see
    build_completed_episode_statistics. year is required (there's no
    sensible "all years" default for a report keyed by calendar year).
    """
    return build_completed_episode_statistics(db, year)


@router.get("/quality-metrics", response_model=list[QualityMetricsMonthRead])
def quality_metrics_report(as_of: date | None = None, db: Session = Depends(get_db)):
    """
    Twelve rows, oldest to newest, the rolling 12-month window ending with
    as_of's calendar month (today if as_of is omitted) — see
    build_quality_metrics. caseload_reach is always null; see
    app/services/quality_metrics.py's module docstring for why.
    """
    return build_quality_metrics(db, as_of or date.today())


@router.get("/drr", response_model=list[DRRClinicRowRead])
def drr_report(year: int, as_of: date | None = None, db: Session = Depends(get_db)):
    """
    The three HEDIS DRR metrics (Follow-Up PHQ-9, Depression Remission,
    Depression Response) for index episodes whose PHQ-9 baseline falls in
    `year`, aggregated by clinic — see build_drr_report's module docstring
    for the denominator convention and the eligible-cohort/window rules.
    as_of defaults to today; pass an earlier date to reproduce a report as
    it would have read at that point in time.
    """
    return build_drr_report(db, year, as_of=as_of)


@router.get("/time-tracker", response_model=list[TimeTrackerPatientRowRead])
def monthly_time_tracker_report(as_of: date | None = None, db: Session = Depends(get_db)):
    """
    Minutes of service per patient, current month plus trailing 12 — see
    build_monthly_time_tracker. Gated on settings.monthly_time_tracker_enabled
    since this report is org-configurable per CLAUDE.md (some orgs don't
    track it at all) — a plain global settings flag rather than a per-org
    database row, per the decision recorded in CLAUDE.md's Monthly Time
    Tracker section. Returns 404 rather than an empty list when disabled,
    so "disabled" can't be confused with "no data."
    """
    if not settings.monthly_time_tracker_enabled:
        raise HTTPException(status_code=404, detail="Monthly Time Tracker is disabled for this organization")
    return build_monthly_time_tracker(db, as_of or date.today())
