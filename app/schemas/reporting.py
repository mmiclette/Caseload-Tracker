from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    ConditionType,
    EndReason,
    MeasureType,
    ProfileSection,
    ProviderRole,
    TreatmentStatusEnum,
)


class ActivePatientRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    needs_psychiatric_review: bool
    safety_risk: bool
    custom_flag_active: bool
    custom_flag_label: str | None

    patient_id: int
    mrn: str
    name: str
    age: int
    status: TreatmentStatusEnum
    psychotropic_medications: bool

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

    initial_assessment_date: date | None
    follow_up_date: date | None
    psychiatric_consultation: str | None
    relapse_prevention_plan_date: date | None

    session_count: int
    weeks_since_initial_assessment: int | None
    minutes_this_month: int


class ClinicalDashboardProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_id: int
    name: str
    role: ProviderRole
    phone: str | None
    email: str | None
    service_begin_date: date


class ClinicalDashboardClinicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_id: str
    is_primary: bool
    service_begin_date: date


class ClinicalDashboardEpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    episode_id: int
    start_date: date
    end_date: date | None
    end_reason: EndReason | None
    baseline_measure_type: MeasureType | None
    baseline_score: int | None
    baseline_date: date | None


class ClinicalDashboardScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    episode_id: int
    measure_type: MeasureType
    score_value: int
    score_date: date


class MeasureTrendPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score_date: date
    score_value: int


class MeasureTrendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    condition: ConditionType
    is_primary: bool
    measure_type: MeasureType
    baseline_score: int | None
    baseline_date: date | None
    latest_score: int | None
    latest_date: date | None
    is_response: bool | None
    is_remission: bool | None
    scores: list[MeasureTrendPointRead]


class ClinicalDashboardProfileEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_entry_id: int
    section: ProfileSection
    sub_field: str
    value: str
    context: str | None
    recorded_date: date
    recorded_by: str | None


class ClinicalDashboardMedicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    medication_id: int
    medication_key: str | None
    medication_name: str
    dose: str | None
    frequency: str | None
    is_current: bool
    stop_reason: str | None


class ClinicalDashboardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    needs_psychiatric_review: bool
    safety_risk: bool
    custom_flag_active: bool
    custom_flag_label: str | None

    current_status: TreatmentStatusEnum | None
    status_changed_date: date | None

    current_providers: list[ClinicalDashboardProviderRead]
    current_clinics: list[ClinicalDashboardClinicRead]
    episodes: list[ClinicalDashboardEpisodeRead]
    symptom_scores: list[ClinicalDashboardScoreRead]
    medications: list[ClinicalDashboardMedicationRead]
    profile_entries: list[ClinicalDashboardProfileEntryRead]
    measure_trends: list[MeasureTrendRead]


class CaseloadStatisticsRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_type: str
    group_key: str
    group_label: str

    caseload_size: int
    patients_with_contact_count: int
    patients_with_contact_percentage: float
    avg_visits_per_patient: float
    avg_session_duration_minutes: float | None
    pct_contacts_with_completed_scale: float
    rpp_count: int
    rpp_percentage: float
    flagged_count: int
    flagged_percentage: float
    with_consultation_count: int
    with_consultation_percentage: float
    not_improving_without_consultation_count: int
    avg_psychiatric_case_reviews: float

    avg_phq9_first: float | None
    avg_phq9_last: float | None
    avg_gad7_first: float | None
    avg_gad7_last: float | None
    avg_pcl5_first: float | None
    avg_pcl5_last: float | None

    combined_response_count: int
    combined_response_denominator: int
    combined_response_percentage: float
    combined_remission_count: int
    combined_remission_denominator: int
    combined_remission_percentage: float

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


class CompletedEpisodeStatisticsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    total_completed_episodes: int
    avg_weeks_in_treatment: float | None
    avg_contacts_per_episode: float | None
    relapse_prevention_plan_count: int
    deactivation_reason_counts: dict[str, int]
    depression_response_count: int
    depression_response_denominator: int
    anxiety_improvement_count: int
    anxiety_improvement_denominator: int
    ptsd_improvement_count: int
    ptsd_improvement_denominator: int


class QualityMetricsMonthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    month: int

    caseload_size: int
    caseload_reach: float | None

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


class DRRClinicRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clinic_id: str
    index_episode_count: int

    follow_up_phq9_count: int
    follow_up_phq9_percentage: float

    depression_remission_count: int
    depression_remission_percentage: float

    depression_response_count: int
    depression_response_percentage: float


class TimeTrackerMonthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    month: int
    minutes: int


class TimeTrackerPatientRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: int
    mrn: str
    name: str
    months: list[TimeTrackerMonthRead]
    total_minutes: int
