"""
Monthly Time Tracker report.

Minutes of service per patient per month, current month plus the trailing
12 months — 13 months total, per CLAUDE.md's literal "current month plus
trailing 12 months" description. This is a CoCM billing reference, since
CoCM billing codes are minutes-of-service thresholds per patient per
month.

"Minutes of service" follows the CTMS's own Minutes This Month tooltip
(docs/ctms-reference/README.md): Care Manager contacts INCLUDING
care_team_collaboration (about-the-patient work is billable time under
CoCM), plus Psychiatric Consultations (consultant time counts too — hence
Consultation.duration_minutes, Phase 9). Failed contact_attempts stay
excluded — outreach that didn't happen isn't billable service.

Patients appear in this report if they have at least one such Contact
anywhere in the 13-month window. This deliberately isn't scoped to only
patients currently on caseload — a program still needs to see billing
minutes for a patient who was active for part of the window and has since
been deactivated.

Per CLAUDE.md, Monthly Time Tracker is org-configurable — some
organizations don't track it at all. That toggle lives on
settings.monthly_time_tracker_enabled (app/core/config.py — a plain global
settings flag, not a per-org database row, since there's no Organization
entity yet for a per-org toggle to live on) and is enforced at the route
layer (app/routes/reports.py), not here: this function always computes the
report; whether an org is allowed to see it is a separate concern kept out
of the report logic itself.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import ContactType
from app.repositories.consultation import ConsultationRepository
from app.repositories.contact import ContactRepository
from app.repositories.patient import PatientRepository
from app.services.date_utils import month_bounds, shift_month

WINDOW_MONTHS = 13  # current month + trailing 12


@dataclass
class TimeTrackerMonth:
    year: int
    month: int
    minutes: int


@dataclass
class TimeTrackerPatientRow:
    patient_id: int
    mrn: str
    name: str
    months: list[TimeTrackerMonth]  # oldest to newest, WINDOW_MONTHS entries
    total_minutes: int


def build_monthly_time_tracker(db: Session, as_of: date) -> list[TimeTrackerPatientRow]:
    month_keys = [shift_month(as_of.year, as_of.month, delta) for delta in range(-(WINDOW_MONTHS - 1), 1)]
    window_start, _ = month_bounds(*month_keys[0])
    _, window_end = month_bounds(*month_keys[-1])

    contacts_repo = ContactRepository(db)
    consultations_repo = ConsultationRepository(db)
    patients_repo = PatientRepository(db)

    patient_ids = sorted(
        set(contacts_repo.list_patient_ids_with_billable_contact_between(window_start, window_end))
        | set(
            consultations_repo.list_patient_ids_with_timed_consultation_between(
                window_start, window_end
            )
        )
    )

    rows = []
    for patient_id in patient_ids:
        patient = patients_repo.get_by_id(patient_id)
        if patient is None:
            continue  # defensive — shouldn't happen given the FK, but never let a report 500 over it

        contacts_in_window = [
            c
            for c in contacts_repo.list_by_patient(patient_id)
            if c.contact_type != ContactType.CONTACT_ATTEMPT
            and c.duration_minutes is not None
            and window_start <= c.contact_date <= window_end
        ]
        consultations_in_window = [
            c
            for c in consultations_repo.list_by_patient(patient_id)
            if c.duration_minutes is not None
            and window_start <= c.consultation_date <= window_end
        ]

        months = []
        total_minutes = 0
        for year, month in month_keys:
            start, end = month_bounds(year, month)
            minutes = sum(
                c.duration_minutes for c in contacts_in_window if start <= c.contact_date <= end
            ) + sum(
                c.duration_minutes
                for c in consultations_in_window
                if start <= c.consultation_date <= end
            )
            months.append(TimeTrackerMonth(year=year, month=month, minutes=minutes))
            total_minutes += minutes

        rows.append(
            TimeTrackerPatientRow(
                patient_id=patient_id,
                mrn=patient.mrn,
                name=patient.name,
                months=months,
                total_minutes=total_minutes,
            )
        )

    return rows
