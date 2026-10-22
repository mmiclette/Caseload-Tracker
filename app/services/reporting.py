"""
Reporting service.

Phase 3 built the two reports a BHCM actually opens every day, per the
CTMS walkthrough: the Reminders landing page (served directly off
ReminderRepository.list_pending — see app/routes/reminders.py, no separate
service needed there) and the Active Patients caseload report, built here.
Phase 4 adds the Clinical Dashboard (a per-patient detail view — see
build_clinical_dashboard below), Caseload Statistics, and Completed
Episode Statistics.

CoCM Quality Metrics, the DRR Report, and Monthly Time Tracker are covered
elsewhere: see app/services/quality_metrics.py and app/services/drr.py,
and CLAUDE.md's Build Status section for what's still open on Monthly
Time Tracker specifically (it needs an org-configuration model this
single-tenant registry doesn't have yet).

This is deliberately simple, per-patient-loop code rather than one large
aggregate SQL query — consistent with the rest of this codebase's service
layer (see EpisodeService.recompute_baseline), and correct at the caseload
sizes a single CoCM program operates at. If this ever needs to scale past
that, the per-patient loop below is the place to replace with batched
queries, not the entry point's shape.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.enums import (
    ConditionType,
    ContactType,
    EndReason,
    MeasureType,
    ProfileSection,
    ProviderRole,
    TreatmentStatusEnum,
)
from app.models.patient import Patient
from app.repositories.care_team_assignment import CareTeamAssignmentRepository
from app.repositories.clinic_assignment import ClinicAssignmentRepository
from app.repositories.consultation import ConsultationRepository
from app.repositories.contact import ContactRepository
from app.repositories.episode import EpisodeRepository
from app.repositories.medication import MedicationRepository
from app.repositories.patient import PatientRepository
from app.repositories.profile_entry import ProfileEntryRepository
from app.repositories.provider import ProviderRepository
from app.repositories.symptom_score import SymptomScoreRepository
from app.repositories.treatment_status import TreatmentStatusRepository
from app.services.scoring import (
    MEASURE_TO_CONDITION,
    SCORE_STALE_DAYS,
    ScoreAssessment,
    ScoreRecord,
    assess_score,
    phq9_score_color,
    resolve_condition_measure,
)

# Contact types that are not patient encounters: a failed outreach attempt
# and about-the-patient care team collaboration. Neither counts as a
# session, engagement, or a scale opportunity — but collaboration minutes
# ARE billable time (see Minutes This Month / Time Tracker).
NON_ENCOUNTER_CONTACT_TYPES = (ContactType.CONTACT_ATTEMPT, ContactType.CARE_TEAM_COLLABORATION)


def _episode_condition(episode) -> ConditionType | None:
    """
    The condition an episode reports under: its primary_diagnosis, or —
    for episodes recorded before diagnoses existed — whatever its baseline
    measure implies (the legacy fallback; see MEASURE_TO_CONDITION).
    """
    if episode.primary_diagnosis is not None:
        return episode.primary_diagnosis
    if episode.baseline_measure_type is not None:
        return MEASURE_TO_CONDITION.get(episode.baseline_measure_type)
    return None


def _primary_measure_assessment(
    episode, episode_scores
) -> tuple[MeasureType, ScoreAssessment] | None:
    """
    The primary-diagnosis-driven outcome for an episode: resolves which
    measure tracks the episode's condition, takes that measure's first
    score in the episode as its baseline and its latest as current, and
    assesses response/remission. None when there's no condition, no
    resolvable measure, or fewer than two same-measure scores to compare.
    """
    condition = _episode_condition(episode)
    if condition is None:
        return None
    measure = resolve_condition_measure(
        condition,
        baseline_measure_type=episode.baseline_measure_type,
        measures_with_scores={s.measure_type for s in episode_scores},
    )
    if measure is None:
        return None
    same_measure = sorted(
        (s for s in episode_scores if s.measure_type == measure),
        key=lambda s: (s.score_date, s.score_id),
    )
    if len(same_measure) < 2:
        return None
    first, latest = same_measure[0], same_measure[-1]
    assessment = assess_score(
        ScoreRecord(measure, first.score_value, first.score_date),
        ScoreRecord(measure, latest.score_value, latest.score_date),
    )
    return measure, assessment


@dataclass
class ActivePatientRow:
    # Flags
    needs_psychiatric_review: bool
    safety_risk: bool
    custom_flag_active: bool
    custom_flag_label: str | None
    # Identity
    patient_id: int
    mrn: str
    name: str
    age: int
    status: TreatmentStatusEnum
    # The AIMS guide's "whether psychotropic medications are prescribed"
    # column. True when the patient has a current Medication picked from
    # the vendored behavioral-health catalog (medication_key set) — every
    # catalog entry is a psychotropic/BH medication by construction. A
    # current free-text medication can't be classified and deliberately
    # doesn't count; this derivation is an assumption, not confirmed CTMS
    # behavior (the walkthrough never showed a medications screen).
    psychotropic_medications: bool
    # PHQ-9 / GAD-7 / PCL-5 first and last, this episode, with the CTMS's
    # confirmed cell indicators (docs/ctms-reference/README.md): *_stale =
    # last score more than 30 days old (the asterisk); *_single_score =
    # only one score on file, so First and Last are the same contact (the
    # CTMS grays the First cell); phq9_last_color = the confirmed
    # red/yellow/green rule (see scoring.phq9_score_color). GAD-7/PCL-5
    # color rules are unconfirmed, so only PHQ-9 gets a color.
    phq9_first: int | None
    phq9_last: int | None
    phq9_stale: bool | None
    phq9_single_score: bool | None
    phq9_last_color: str | None
    gad7_first: int | None
    gad7_last: int | None
    gad7_stale: bool | None
    gad7_single_score: bool | None
    pcl5_first: int | None
    pcl5_last: int | None
    pcl5_stale: bool | None
    pcl5_single_score: bool | None
    # Contacts group
    initial_assessment_date: date | None
    follow_up_date: date | None
    psychiatric_consultation: str | None  # an ISO date string, or "CONSIDER"
    relapse_prevention_plan_date: date | None
    # Trailing columns
    session_count: int
    weeks_since_initial_assessment: int | None
    minutes_this_month: int


@dataclass
class _MeasureCells:
    """One measure's caseload-list cells: values plus display indicators."""

    first: int | None = None
    last: int | None = None
    stale: bool | None = None  # last score more than SCORE_STALE_DAYS old
    single_score: bool | None = None  # only one score on file


def _measure_cells(scores, measure_type: MeasureType, as_of: date) -> _MeasureCells:
    matching = sorted(
        (s for s in scores if s.measure_type == measure_type),
        key=lambda s: (s.score_date, s.score_id),
    )
    if not matching:
        return _MeasureCells()
    first, last = matching[0], matching[-1]
    return _MeasureCells(
        first=first.score_value,
        last=last.score_value,
        stale=(as_of - last.score_date).days > SCORE_STALE_DAYS,
        single_score=len(matching) == 1,
    )


def build_active_patients_report(
    db: Session,
    *,
    payer: str | None = None,
    clinic_id: str | None = None,
    provider_id: int | None = None,
    as_of: date | None = None,
) -> list[ActivePatientRow]:
    """
    as_of defaults to today; tests pass it explicitly so "weeks since" and
    "minutes this month" are deterministic instead of depending on the
    clock the test happens to run on.
    """
    as_of = as_of or date.today()

    patients = PatientRepository(db)
    episodes = EpisodeRepository(db)
    statuses = TreatmentStatusRepository(db)
    contacts = ContactRepository(db)
    scores = SymptomScoreRepository(db)
    consultations = ConsultationRepository(db)
    clinic_assignments = ClinicAssignmentRepository(db)
    care_team = CareTeamAssignmentRepository(db)
    medications = MedicationRepository(db)

    candidate_patient_ids: set[int] | None = None
    if clinic_id is not None:
        candidate_patient_ids = set(clinic_assignments.list_patient_ids_for_clinic(clinic_id))
    if provider_id is not None:
        provider_patient_ids = set(care_team.list_patient_ids_for_provider(provider_id))
        candidate_patient_ids = (
            provider_patient_ids
            if candidate_patient_ids is None
            else candidate_patient_ids & provider_patient_ids
        )

    if candidate_patient_ids is not None:
        all_patients = [p for p in patients.list(limit=100_000) if p.patient_id in candidate_patient_ids]
    else:
        all_patients = patients.list(limit=100_000)

    rows: list[ActivePatientRow] = []
    for patient in all_patients:
        if payer is not None and patient.payer != payer:
            continue

        current_status = statuses.get_current(patient.patient_id)
        if current_status is None or current_status.status == TreatmentStatusEnum.DEACTIVATED:
            continue

        episode = episodes.get_open_episode(patient.patient_id)
        if episode is None:
            continue

        episode_contacts = contacts.list_by_episode(episode.episode_id)
        episode_scores = scores.list_by_episode(episode.episode_id)

        initial_assessments = [
            c for c in episode_contacts if c.contact_type == ContactType.INITIAL_ASSESSMENT
        ]
        follow_ups = [c for c in episode_contacts if c.contact_type == ContactType.FOLLOW_UP]
        rpp_contacts = [
            c for c in episode_contacts if c.contact_type == ContactType.RELAPSE_PREVENTION_PLAN
        ]

        ia_date = min((c.contact_date for c in initial_assessments), default=None)
        fu_date = max((c.contact_date for c in follow_ups), default=None)
        rpp_date = max((c.contact_date for c in rpp_contacts), default=None)

        if patient.needs_psychiatric_review:
            pc_value = "CONSIDER"
        else:
            last_consultation = max(
                (c.consultation_date for c in consultations.list_by_patient(patient.patient_id)),
                default=None,
            )
            pc_value = last_consultation.isoformat() if last_consultation else None

        phq9 = _measure_cells(episode_scores, MeasureType.PHQ9, as_of)
        gad7 = _measure_cells(episode_scores, MeasureType.GAD7, as_of)
        pcl5 = _measure_cells(episode_scores, MeasureType.PCL5, as_of)
        phq9_last_color = (
            phq9_score_color(phq9.first, phq9.last) if phq9.last is not None else None
        )

        session_count = sum(
            1 for c in episode_contacts if c.contact_type not in NON_ENCOUNTER_CONTACT_TYPES
        )
        weeks_since_ia = (as_of - ia_date).days // 7 if ia_date else None

        # Per the CTMS's own tooltip: minutes include Care Manager contacts
        # (care team collaboration included) AND Psychiatric Consultations.
        # contact_attempt is excluded — outreach that never reached the
        # patient isn't service time. That exclusion is the same rule
        # Monthly Time Tracker applies (see app/services/time_tracker.py);
        # this column and that report answer the same question ("minutes of
        # service this month") and must never disagree. They did until
        # 2026-08-12, when the frontend's contact form made it possible to
        # put minutes on an attempt and the pressure test caught the 5-minute
        # gap between the two surfaces.
        all_patient_contacts = contacts.list_by_patient(patient.patient_id)
        minutes_this_month = sum(
            c.duration_minutes or 0
            for c in all_patient_contacts
            if c.contact_type != ContactType.CONTACT_ATTEMPT
            and c.contact_date.year == as_of.year
            and c.contact_date.month == as_of.month
        ) + sum(
            c.duration_minutes or 0
            for c in consultations.list_by_patient(patient.patient_id)
            if c.consultation_date.year == as_of.year and c.consultation_date.month == as_of.month
        )

        rows.append(
            ActivePatientRow(
                needs_psychiatric_review=patient.needs_psychiatric_review,
                safety_risk=patient.safety_risk,
                custom_flag_active=patient.custom_flag_active,
                custom_flag_label=patient.custom_flag_label,
                patient_id=patient.patient_id,
                mrn=patient.mrn,
                name=patient.name,
                age=patient.age,
                status=current_status.status,
                psychotropic_medications=any(
                    m.medication_key is not None
                    for m in medications.list_current_by_patient(patient.patient_id)
                ),
                phq9_first=phq9.first,
                phq9_last=phq9.last,
                phq9_stale=phq9.stale,
                phq9_single_score=phq9.single_score,
                phq9_last_color=phq9_last_color,
                gad7_first=gad7.first,
                gad7_last=gad7.last,
                gad7_stale=gad7.stale,
                gad7_single_score=gad7.single_score,
                pcl5_first=pcl5.first,
                pcl5_last=pcl5.last,
                pcl5_stale=pcl5.stale,
                pcl5_single_score=pcl5.single_score,
                initial_assessment_date=ia_date,
                follow_up_date=fu_date,
                psychiatric_consultation=pc_value,
                relapse_prevention_plan_date=rpp_date,
                session_count=session_count,
                weeks_since_initial_assessment=weeks_since_ia,
                minutes_this_month=minutes_this_month,
            )
        )

    return rows


# --- Clinical Dashboard ---------------------------------------------------


@dataclass
class ClinicalDashboardProvider:
    provider_id: int
    name: str
    role: ProviderRole
    phone: str | None
    email: str | None
    service_begin_date: date


@dataclass
class ClinicalDashboardClinic:
    clinic_id: str
    is_primary: bool
    service_begin_date: date


@dataclass
class ClinicalDashboardEpisode:
    episode_id: int
    start_date: date
    end_date: date | None
    end_reason: EndReason | None
    baseline_measure_type: MeasureType | None
    baseline_score: int | None
    baseline_date: date | None


@dataclass
class ClinicalDashboardScore:
    episode_id: int
    measure_type: MeasureType
    score_value: int
    score_date: date


@dataclass
class MeasureTrendPoint:
    score_date: date
    score_value: int


@dataclass
class MeasureTrend:
    """
    One top-of-dashboard graph: the treated condition, the measure that
    tracks it, that measure's score series in the reference episode, and
    response/remission vs. the measure's own first-in-episode baseline —
    computed here (via assess_score) so thresholds stay in one place and
    the frontend only draws.
    """

    condition: ConditionType
    is_primary: bool
    measure_type: MeasureType
    baseline_score: int | None
    baseline_date: date | None
    latest_score: int | None
    latest_date: date | None
    is_response: bool | None  # None until there are >= 2 scores to compare
    is_remission: bool | None  # None until there's at least 1 score
    scores: list[MeasureTrendPoint]


@dataclass
class ClinicalDashboardProfileEntry:
    profile_entry_id: int
    section: ProfileSection
    sub_field: str
    value: str
    context: str | None
    recorded_date: date
    recorded_by: str | None


@dataclass
class ClinicalDashboardMedication:
    medication_id: int
    medication_key: str | None
    medication_name: str
    dose: str | None
    frequency: str | None
    is_current: bool
    stop_reason: str | None


@dataclass
class ClinicalDashboard:
    # Enrollment info and demographics
    patient_id: int
    mrn: str
    name: str
    age: int
    date_of_birth: date
    race_ethnicity: list[str] | None
    payer: str
    program_eligibility: dict | None
    consent_date: date
    enrollment_date: date
    deactivation_date: date | None
    # Flags
    needs_psychiatric_review: bool
    safety_risk: bool
    custom_flag_active: bool
    custom_flag_label: str | None
    # Status
    current_status: TreatmentStatusEnum | None
    status_changed_date: date | None
    # Current providers / current clinics
    current_providers: list[ClinicalDashboardProvider]
    current_clinics: list[ClinicalDashboardClinic]
    # Episode history and graphed symptom scores over time
    episodes: list[ClinicalDashboardEpisode]
    symptom_scores: list[ClinicalDashboardScore]
    # Current medications first, then past (with stop reasons)
    medications: list[ClinicalDashboardMedication]
    # Append-only profile sections, grouped by section and sub-field with
    # the newest entry first per sub-field (see ProfileEntryRepository) —
    # the newest is the current value, the rest are its history.
    profile_entries: list[ClinicalDashboardProfileEntry]
    # Top-of-page graphs, one per treated diagnosis (primary first) on the
    # reference episode (the open episode, or the most recent one).
    measure_trends: list[MeasureTrend]


def build_clinical_dashboard(db: Session, patient_id: int) -> ClinicalDashboard:
    """
    The CTMS's per-patient Clinical Dashboard. Its "Customize Dashboard
    View" toggle (which sections show) is a frontend display preference,
    not a backend concern — this endpoint always returns every section;
    the frontend decides what to render, the same way the Active Patients
    report's Deactivate action is a UI affordance against an existing
    endpoint rather than a report column.
    """
    patients = PatientRepository(db)
    patient = patients.get_by_id(patient_id)
    if patient is None:
        raise ValueError(f"Patient {patient_id} not found")

    current_status = TreatmentStatusRepository(db).get_current(patient_id)

    current_providers = [
        ClinicalDashboardProvider(
            provider_id=a.provider_id,
            name=a.provider.name,
            role=a.provider.role,
            phone=a.provider.phone,
            email=a.provider.email,
            service_begin_date=a.service_begin_date,
        )
        for a in CareTeamAssignmentRepository(db).list_current_by_patient(patient_id)
    ]

    current_clinics = [
        ClinicalDashboardClinic(
            clinic_id=c.clinic_id, is_primary=c.is_primary, service_begin_date=c.service_begin_date
        )
        for c in ClinicAssignmentRepository(db).list_current_by_patient(patient_id)
    ]

    episodes = [
        ClinicalDashboardEpisode(
            episode_id=e.episode_id,
            start_date=e.start_date,
            end_date=e.end_date,
            end_reason=e.end_reason,
            baseline_measure_type=e.baseline_measure_type,
            baseline_score=e.baseline_score,
            baseline_date=e.baseline_date,
        )
        for e in EpisodeRepository(db).list_by_patient(patient_id)
    ]

    symptom_scores = [
        ClinicalDashboardScore(
            episode_id=s.episode_id,
            measure_type=s.measure_type,
            score_value=s.score_value,
            score_date=s.score_date,
        )
        for s in sorted(SymptomScoreRepository(db).list_by_patient(patient_id), key=lambda s: s.score_date)
    ]

    dashboard_medications = [
        ClinicalDashboardMedication(
            medication_id=m.medication_id,
            medication_key=m.medication_key,
            medication_name=m.medication_name,
            dose=m.dose,
            frequency=m.frequency,
            is_current=m.is_current,
            stop_reason=m.stop_reason,
        )
        for m in MedicationRepository(db).list_by_patient(patient_id)
    ]

    all_episodes = EpisodeRepository(db).list_by_patient(patient_id)
    reference_episode = next((e for e in all_episodes if e.end_date is None), None)
    if reference_episode is None and all_episodes:
        reference_episode = max(all_episodes, key=lambda e: e.start_date)

    measure_trends: list[MeasureTrend] = []
    if reference_episode is not None:
        episode_scores = SymptomScoreRepository(db).list_by_episode(reference_episode.episode_id)
        measures_with_scores = {s.measure_type for s in episode_scores}

        diagnoses: list[tuple[ConditionType, bool]] = []
        if reference_episode.primary_diagnosis is not None:
            diagnoses.append((reference_episode.primary_diagnosis, True))
            if reference_episode.secondary_diagnosis is not None:
                diagnoses.append((reference_episode.secondary_diagnosis, False))
        else:
            legacy_condition = _episode_condition(reference_episode)
            if legacy_condition is not None:
                diagnoses.append((legacy_condition, True))

        for condition, is_primary in diagnoses:
            measure = resolve_condition_measure(
                condition,
                baseline_measure_type=reference_episode.baseline_measure_type,
                measures_with_scores=measures_with_scores,
            )
            if measure is None:
                continue  # substance_use until AUDIT-C/DAST-10 exist
            series = sorted(
                (s for s in episode_scores if s.measure_type == measure),
                key=lambda s: (s.score_date, s.score_id),
            )
            assessment = None
            if series:
                first, latest = series[0], series[-1]
                assessment = assess_score(
                    ScoreRecord(measure, first.score_value, first.score_date),
                    ScoreRecord(measure, latest.score_value, latest.score_date),
                )
            measure_trends.append(
                MeasureTrend(
                    condition=condition,
                    is_primary=is_primary,
                    measure_type=measure,
                    baseline_score=series[0].score_value if series else None,
                    baseline_date=series[0].score_date if series else None,
                    latest_score=series[-1].score_value if series else None,
                    latest_date=series[-1].score_date if series else None,
                    is_response=(
                        assessment.is_response if assessment and len(series) >= 2 else None
                    ),
                    is_remission=assessment.is_remission if assessment else None,
                    scores=[MeasureTrendPoint(s.score_date, s.score_value) for s in series],
                )
            )

    profile_entries = [
        ClinicalDashboardProfileEntry(
            profile_entry_id=e.profile_entry_id,
            section=e.section,
            sub_field=e.sub_field,
            value=e.value,
            context=e.context,
            recorded_date=e.recorded_date,
            recorded_by=e.recorded_by,
        )
        for e in ProfileEntryRepository(db).list_by_patient(patient_id)
    ]

    return ClinicalDashboard(
        patient_id=patient.patient_id,
        mrn=patient.mrn,
        name=patient.name,
        age=patient.age,
        date_of_birth=patient.date_of_birth,
        race_ethnicity=patient.race_ethnicity,
        payer=patient.payer,
        program_eligibility=patient.program_eligibility,
        consent_date=patient.consent_date,
        enrollment_date=patient.enrollment_date,
        deactivation_date=patient.deactivation_date,
        needs_psychiatric_review=patient.needs_psychiatric_review,
        safety_risk=patient.safety_risk,
        custom_flag_active=patient.custom_flag_active,
        custom_flag_label=patient.custom_flag_label,
        current_status=current_status.status if current_status else None,
        status_changed_date=current_status.status_changed_date if current_status else None,
        current_providers=current_providers,
        current_clinics=current_clinics,
        episodes=episodes,
        symptom_scores=symptom_scores,
        medications=dashboard_medications,
        profile_entries=profile_entries,
        measure_trends=measure_trends,
    )


# --- Caseload Statistics ---------------------------------------------------


# "Not improving without consultation" window, per the AIMS guide's own
# caseload-summary line ("not improving and ... not been reviewed with the
# Psychiatric Consultant within the past two months").
NOT_IMPROVING_REVIEW_WINDOW_DAYS = 60


@dataclass
class CaseloadStatisticsRow:
    group_type: str  # "provider" or "clinic"
    group_key: str  # provider_id (as a string) or clinic_id
    group_label: str  # "Priya Nandakumar (care_manager)", or the clinic_id

    caseload_size: int
    # CTMS "Pts w/ B/C": patients with at least one completed encounter in
    # their current episode. All percentages in this row use caseload_size
    # as the denominator — the CTMS screenshot's own denominators are
    # ambiguous at the available resolution, so one consistent, documented
    # convention beats a reverse-engineered guess.
    patients_with_contact_count: int
    patients_with_contact_percentage: float
    avg_visits_per_patient: float
    avg_session_duration_minutes: float | None
    pct_contacts_with_completed_scale: float
    # CTMS "# in R/P": current Treatment Status is relapse_prevention_plan.
    rpp_count: int
    rpp_percentage: float
    # CTMS "# Flagged": needs_psychiatric_review currently set.
    flagged_count: int
    flagged_percentage: float
    # CTMS "# w/ P/C": at least one Consultation during the current episode.
    with_consultation_count: int
    with_consultation_percentage: float
    # AIMS "not improving and not reviewed within the past two months":
    # primary-measure outcome exists, is not a response, and no
    # Consultation in the last NOT_IMPROVING_REVIEW_WINDOW_DAYS. Patients
    # without a follow-up score can't be assessed and don't count.
    not_improving_without_consultation_count: int
    avg_psychiatric_case_reviews: float

    # Average first (intake) and most recent scores per measure.
    avg_phq9_first: float | None
    avg_phq9_last: float | None
    avg_gad7_first: float | None
    avg_gad7_last: float | None
    avg_pcl5_first: float | None
    avg_pcl5_last: float | None

    # Combined response/remission first, then per-condition (Matt,
    # 2026-08-07: "maybe we have combined, then depression and anxiety
    # metrics"). Combined pools the primary-diagnosis-driven depression and
    # anxiety outcomes — the buckets are disjoint (each patient counts
    # toward exactly one), so pooling never double-counts. Unscored
    # measures (PCL-5, pediatric) stay out of all of these.
    combined_response_count: int
    combined_response_denominator: int
    combined_response_percentage: float
    combined_remission_count: int
    combined_remission_denominator: int
    combined_remission_percentage: float

    # Primary-diagnosis-driven outcome rates (2026-08 design decision): a
    # patient counts toward exactly one condition's rates — the measure
    # mapped to their episode's primary diagnosis (anxiety-primary tracks
    # GAD-7, depression-primary tracks PHQ-9; legacy episodes without a
    # diagnosis fall back to what their baseline measure implies). Rates
    # are both a fraction and a percentage, per CLAUDE.md. denominator is
    # the number of such patients with at least two same-measure scores in
    # the current episode — a patient without a follow-up score can't have
    # an outcome yet. Pediatric-measure patients (SMFQ/SCARED) are excluded
    # from these rates until their thresholds are confirmed.
    depression_response_count: int
    depression_response_denominator: int
    depression_response_percentage: float
    depression_remission_count: int
    depression_remission_denominator: int
    depression_remission_percentage: float
    anxiety_response_count: int
    anxiety_response_denominator: int
    anxiety_response_percentage: float
    anxiety_remission_count: int
    anxiety_remission_denominator: int
    anxiety_remission_percentage: float


def _percentage(count: int, denominator: int) -> float:
    return round(100 * count / denominator, 1) if denominator else 0.0


def _active_patient_ids(db: Session, candidate_ids: list[int]) -> list[int]:
    statuses = TreatmentStatusRepository(db)
    return [
        pid
        for pid in candidate_ids
        if (current := statuses.get_current(pid)) is not None
        and current.status != TreatmentStatusEnum.DEACTIVATED
    ]


def _compute_caseload_metrics(db: Session, patient_ids: list[int], as_of: date) -> dict:
    """
    All figures are computed over each patient's currently open episode —
    "current caseload," in the CTMS's own framing, means what's happening
    right now, not a full lifetime history. A patient with no open episode
    (e.g. between episodes) contributes to caseload_size but nothing else.
    as_of only anchors the "past two months" window for the
    not-improving-without-consultation count.
    """
    episodes_repo = EpisodeRepository(db)
    contacts_repo = ContactRepository(db)
    scores_repo = SymptomScoreRepository(db)
    consultations_repo = ConsultationRepository(db)
    patients_repo = PatientRepository(db)
    statuses_repo = TreatmentStatusRepository(db)

    total_contacts = 0
    total_minutes = 0
    minutes_count = 0
    contacts_with_scale = 0
    total_case_reviews = 0
    patients_with_contact = 0
    rpp_patients = 0
    flagged_patients = 0
    with_consultation = 0
    not_improving_without_pc = 0
    first_values: dict[MeasureType, list[int]] = {m: [] for m in (MeasureType.PHQ9, MeasureType.GAD7, MeasureType.PCL5)}
    last_values: dict[MeasureType, list[int]] = {m: [] for m in (MeasureType.PHQ9, MeasureType.GAD7, MeasureType.PCL5)}
    dep_response = dep_remission = dep_denominator = 0
    anx_response = anx_remission = anx_denominator = 0

    review_window_start = as_of - timedelta(days=NOT_IMPROVING_REVIEW_WINDOW_DAYS)

    for patient_id in patient_ids:
        consultations = consultations_repo.list_by_patient(patient_id)
        total_case_reviews += len(consultations)

        patient = patients_repo.get_by_id(patient_id)
        if patient is not None and patient.needs_psychiatric_review:
            flagged_patients += 1
        current_status = statuses_repo.get_current(patient_id)
        if current_status is not None and current_status.status == TreatmentStatusEnum.RELAPSE_PREVENTION_PLAN:
            rpp_patients += 1

        episode = episodes_repo.get_open_episode(patient_id)
        if episode is None:
            continue

        if any(c.consultation_date >= episode.start_date for c in consultations):
            with_consultation += 1

        episode_contacts = [
            c
            for c in contacts_repo.list_by_episode(episode.episode_id)
            if c.contact_type not in NON_ENCOUNTER_CONTACT_TYPES
        ]
        total_contacts += len(episode_contacts)
        if episode_contacts:
            patients_with_contact += 1

        episode_scores = scores_repo.list_by_episode(episode.episode_id)
        contact_ids_with_scores = {s.contact_id for s in episode_scores}
        for contact in episode_contacts:
            if contact.duration_minutes is not None:
                total_minutes += contact.duration_minutes
                minutes_count += 1
            if contact.contact_id in contact_ids_with_scores:
                contacts_with_scale += 1

        first_by_measure = {}
        latest_by_measure = {}
        for score in sorted(episode_scores, key=lambda s: (s.score_date, s.score_id)):
            first_by_measure.setdefault(score.measure_type, score)  # first write wins
            latest_by_measure[score.measure_type] = score  # last write (latest date) wins

        for measure in first_values:
            if measure in first_by_measure:
                first_values[measure].append(first_by_measure[measure].score_value)
                last_values[measure].append(latest_by_measure[measure].score_value)

        outcome = _primary_measure_assessment(episode, episode_scores)
        if outcome is not None:
            measure, assessment = outcome
            if measure == MeasureType.PHQ9:
                dep_denominator += 1
                dep_response += int(assessment.is_response)
                dep_remission += int(assessment.is_remission)
            elif measure == MeasureType.GAD7:
                anx_denominator += 1
                anx_response += int(assessment.is_response)
                anx_remission += int(assessment.is_remission)
            # Pediatric measures (SMFQ/SCARED) and PCL-5/Vanderbilt fall
            # through: no confirmed thresholds yet, so they don't inflate
            # these denominators with outcomes that always read False.

            if measure in (MeasureType.PHQ9, MeasureType.GAD7) and not assessment.is_response:
                recently_reviewed = any(
                    c.consultation_date >= review_window_start for c in consultations
                )
                if not recently_reviewed:
                    not_improving_without_pc += 1

    def _avg(values: list[int]) -> float | None:
        return round(sum(values) / len(values), 1) if values else None

    caseload_size = len(patient_ids)
    return dict(
        caseload_size=caseload_size,
        patients_with_contact_count=patients_with_contact,
        patients_with_contact_percentage=_percentage(patients_with_contact, caseload_size),
        avg_visits_per_patient=round(total_contacts / caseload_size, 2) if caseload_size else 0.0,
        avg_session_duration_minutes=round(total_minutes / minutes_count, 1) if minutes_count else None,
        pct_contacts_with_completed_scale=_percentage(contacts_with_scale, total_contacts),
        rpp_count=rpp_patients,
        rpp_percentage=_percentage(rpp_patients, caseload_size),
        flagged_count=flagged_patients,
        flagged_percentage=_percentage(flagged_patients, caseload_size),
        with_consultation_count=with_consultation,
        with_consultation_percentage=_percentage(with_consultation, caseload_size),
        not_improving_without_consultation_count=not_improving_without_pc,
        avg_psychiatric_case_reviews=round(total_case_reviews / caseload_size, 2) if caseload_size else 0.0,
        avg_phq9_first=_avg(first_values[MeasureType.PHQ9]),
        avg_phq9_last=_avg(last_values[MeasureType.PHQ9]),
        avg_gad7_first=_avg(first_values[MeasureType.GAD7]),
        avg_gad7_last=_avg(last_values[MeasureType.GAD7]),
        avg_pcl5_first=_avg(first_values[MeasureType.PCL5]),
        avg_pcl5_last=_avg(last_values[MeasureType.PCL5]),
        combined_response_count=dep_response + anx_response,
        combined_response_denominator=dep_denominator + anx_denominator,
        combined_response_percentage=_percentage(
            dep_response + anx_response, dep_denominator + anx_denominator
        ),
        combined_remission_count=dep_remission + anx_remission,
        combined_remission_denominator=dep_denominator + anx_denominator,
        combined_remission_percentage=_percentage(
            dep_remission + anx_remission, dep_denominator + anx_denominator
        ),
        depression_response_count=dep_response,
        depression_response_denominator=dep_denominator,
        depression_response_percentage=_percentage(dep_response, dep_denominator),
        depression_remission_count=dep_remission,
        depression_remission_denominator=dep_denominator,
        depression_remission_percentage=_percentage(dep_remission, dep_denominator),
        anxiety_response_count=anx_response,
        anxiety_response_denominator=anx_denominator,
        anxiety_response_percentage=_percentage(anx_response, anx_denominator),
        anxiety_remission_count=anx_remission,
        anxiety_remission_denominator=anx_denominator,
        anxiety_remission_percentage=_percentage(anx_remission, anx_denominator),
    )


def build_caseload_statistics(
    db: Session, *, group_by: str = "provider", as_of: date | None = None
) -> list[CaseloadStatisticsRow]:
    """
    group_by="provider" rolls up by whichever Provider currently has
    patients on their care team (Care Manager, PCP, or Psychiatric
    Consultant alike — CLAUDE.md's "per-Psychiatric-Consultant, per-PCP"
    phrasing is just this same rollup filtered to a role, which the caller
    can do client-side from group_label). group_by="clinic" rolls up by
    current Clinic Assignment instead.
    """
    if group_by not in ("provider", "clinic"):
        raise ValueError(f"Unknown group_by: {group_by!r} (expected 'provider' or 'clinic')")

    as_of = as_of or date.today()
    rows: list[CaseloadStatisticsRow] = []

    if group_by == "provider":
        care_team = CareTeamAssignmentRepository(db)
        providers = ProviderRepository(db)
        for provider_id in care_team.list_current_provider_ids():
            provider = providers.get_by_id(provider_id)
            if provider is None:
                continue
            active_ids = _active_patient_ids(db, care_team.list_patient_ids_for_provider(provider_id))
            metrics = _compute_caseload_metrics(db, active_ids, as_of)
            rows.append(
                CaseloadStatisticsRow(
                    group_type="provider",
                    group_key=str(provider_id),
                    group_label=f"{provider.name} ({provider.role.value})",
                    **metrics,
                )
            )
    else:
        clinics = ClinicAssignmentRepository(db)
        for clinic_id in clinics.list_current_clinic_ids():
            active_ids = _active_patient_ids(db, clinics.list_patient_ids_for_clinic(clinic_id))
            metrics = _compute_caseload_metrics(db, active_ids, as_of)
            rows.append(
                CaseloadStatisticsRow(
                    group_type="clinic", group_key=clinic_id, group_label=clinic_id, **metrics
                )
            )

    return rows


# --- Completed Episode Statistics ------------------------------------------


@dataclass
class CompletedEpisodeStatistics:
    year: int
    total_completed_episodes: int
    avg_weeks_in_treatment: float | None
    avg_contacts_per_episode: float | None
    relapse_prevention_plan_count: int
    # EndReason.value -> count, plus "not_recorded" for a closed episode
    # with no end_reason set — a real data-quality state worth surfacing
    # rather than silently dropping from the breakdown.
    deactivation_reason_counts: dict[str, int]
    depression_response_count: int
    depression_response_denominator: int
    anxiety_improvement_count: int
    anxiety_improvement_denominator: int
    # PCL-5 thresholds are unconfirmed (see Symptom Score in CLAUDE.md) —
    # assess_score() already returns is_response=False unconditionally for
    # PCL5, so this will always read 0/denominator. That's the correct
    # conservative default, not a bug; don't "fix" it by inventing a
    # threshold.
    ptsd_improvement_count: int
    ptsd_improvement_denominator: int


def build_completed_episode_statistics(db: Session, year: int) -> CompletedEpisodeStatistics:
    episodes_repo = EpisodeRepository(db)
    contacts_repo = ContactRepository(db)
    scores_repo = SymptomScoreRepository(db)

    cohort = episodes_repo.list_completed_in_year(year)
    total = len(cohort)

    deactivation_reason_counts: dict[str, int] = {reason.value: 0 for reason in EndReason}
    deactivation_reason_counts["not_recorded"] = 0

    total_weeks = 0.0
    total_contacts = 0
    rpp_count = 0
    dep_response = dep_denominator = 0
    anx_improvement = anx_denominator = 0
    ptsd_improvement = ptsd_denominator = 0

    for episode in cohort:
        total_weeks += (episode.end_date - episode.start_date).days / 7

        episode_contacts = [
            c
            for c in contacts_repo.list_by_episode(episode.episode_id)
            if c.contact_type not in NON_ENCOUNTER_CONTACT_TYPES
        ]
        total_contacts += len(episode_contacts)
        if any(c.contact_type == ContactType.RELAPSE_PREVENTION_PLAN for c in episode_contacts):
            rpp_count += 1

        if episode.end_reason is not None:
            deactivation_reason_counts[episode.end_reason.value] += 1
        else:
            deactivation_reason_counts["not_recorded"] += 1

        # Primary-diagnosis-driven, same rule as Caseload Statistics: each
        # episode contributes to exactly one condition's outcome, via the
        # measure its primary diagnosis maps to (legacy episodes fall back
        # to their baseline measure's implied condition).
        episode_scores = scores_repo.list_by_episode(episode.episode_id)
        outcome = _primary_measure_assessment(episode, episode_scores)
        if outcome is not None:
            measure, assessment = outcome
            if measure == MeasureType.PHQ9:
                dep_denominator += 1
                dep_response += int(assessment.is_response)
            elif measure == MeasureType.GAD7:
                anx_denominator += 1
                anx_improvement += int(assessment.is_response)
            elif measure == MeasureType.PCL5:
                ptsd_denominator += 1
                ptsd_improvement += int(assessment.is_response)

    return CompletedEpisodeStatistics(
        year=year,
        total_completed_episodes=total,
        avg_weeks_in_treatment=round(total_weeks / total, 1) if total else None,
        avg_contacts_per_episode=round(total_contacts / total, 1) if total else None,
        relapse_prevention_plan_count=rpp_count,
        deactivation_reason_counts=deactivation_reason_counts,
        depression_response_count=dep_response,
        depression_response_denominator=dep_denominator,
        anxiety_improvement_count=anx_improvement,
        anxiety_improvement_denominator=anx_denominator,
        ptsd_improvement_count=ptsd_improvement,
        ptsd_improvement_denominator=ptsd_denominator,
    )
