/**
 * API response types, mirrored from app/schemas/*.py.
 *
 * Hand-written rather than generated from /openapi.json: the API is small
 * and stable, and hand-written types let us document the non-obvious
 * fields (the caseload cell indicators, the "CONSIDER" sentinel) right
 * where a component reads them. If these drift from the backend, the
 * pressure test and route tests are what catch it server-side; here,
 * `npm run typecheck` catches our own misuse.
 */

export type TreatmentStatus =
  | 'active_treatment'
  | 'relapse_prevention_plan'
  | 'deactivated'

export type ContactType =
  | 'initial_assessment'
  | 'follow_up'
  | 'relapse_prevention_plan'
  | 'contact_attempt'
  | 'care_team_collaboration'

export type ContactLocation = 'phone' | 'in_clinic' | 'virtual'

export type MeasureType =
  | 'PHQ9'
  | 'GAD7'
  | 'PCL5'
  | 'SCARED'
  | 'SMFQ'
  | 'VANDERBILT'
  | 'OTHER'

export type ConditionType =
  | 'depression'
  | 'anxiety'
  | 'ptsd'
  | 'adhd'
  | 'substance_use'

export type CareTeamRole =
  | 'care_manager'
  | 'primary_care_provider'
  | 'psychiatric_consultant'

export type ProviderRole = CareTeamRole | 'clinic_supervisor' | 'data_analyst'

export type ReminderType = 'appointment' | 'referral_followup'
export type ReminderStatus = 'pending' | 'completed' | 'dismissed'

export type MedicationConfirmation =
  | 'confirmed_with_patient'
  | 'confirmed_in_medical_record'
  | 'deferred'

export type EndReason =
  | 'achieved_goals'
  | 'not_engaged'
  | 'patient_choice'
  | 'patient_no_longer_available'
  | 'patient_died'
  | 'patient_died_by_suicide'
  | 'other'

export type ProfileSection =
  | 'behavioral_health'
  | 'current_medications'
  | 'medical_profile'
  | 'safety_and_risk'
  | 'substance_use'
  | 'social_environmental'

export interface Provider {
  provider_id: number
  name: string
  role: ProviderRole
  phone: string | null
  email: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
  provider: Provider
}

export interface Patient {
  patient_id: number
  mrn: string
  name: string
  payer: string
  program_eligibility: Record<string, unknown> | null
  date_of_birth: string
  race_ethnicity: string[] | null
  consent_date: string
  enrollment_date: string
  deactivation_date: string | null
  needs_psychiatric_review: boolean
  safety_risk: boolean
  custom_flag_active: boolean
  custom_flag_label: string | null
  age: number
}

export interface Episode {
  episode_id: number
  patient_id: number
  start_date: string
  primary_diagnosis: ConditionType | null
  secondary_diagnosis: ConditionType | null
  baseline_measure_type: MeasureType | null
  baseline_score: number | null
  baseline_date: string | null
  end_date: string | null
  end_reason: EndReason | null
}

export interface Contact {
  contact_id: number
  patient_id: number
  episode_id: number | null
  provider_id: number | null
  contact_type: ContactType
  contact_date: string
  location: ContactLocation | null
  duration_minutes: number | null
  discuss_with_psychiatric_consultant: boolean
  notes_for_consultant: string | null
  notes: string | null
  other_treatments: string | null
  personal_warning_signs: string | null
  stress_reduction_plan: string | null
  additional_comments: string | null
  medications_confirmation: MedicationConfirmation | null
  attempt_number: number | null
}

export interface SymptomScore {
  score_id: number
  episode_id: number
  patient_id: number
  contact_id: number
  measure_type: MeasureType
  score_value: number
  score_date: string
  recorded_by: string | null
}

export interface Consultation {
  consultation_id: number
  patient_id: number
  provider_id: number | null
  consultation_date: string
  duration_minutes: number | null
  recommendations_forwarded: boolean
  flagged_for_next_review: boolean
  flag_reason: string | null
  notes: string | null
}

export interface Reminder {
  reminder_id: number
  patient_id: number
  episode_id: number | null
  referral_id: number | null
  reminder_type: ReminderType
  due_date: string
  status: ReminderStatus
  notes: string | null
}

export interface Medication {
  medication_id: number
  patient_id: number
  medication_key: string | null
  medication_name: string
  dose: string | null
  frequency: string | null
  is_current: boolean
  stop_reason: string | null
  recorded_by: string | null
}

export interface CatalogEntry {
  key: string
  display: string
  med_class: string
  doses: string[]
}

export interface ProfileEntry {
  profile_entry_id: number
  patient_id: number
  section: ProfileSection
  sub_field: string
  value: string
  context: string | null
  recorded_date: string
  recorded_by: string | null
}

export interface ProfileSectionDefinition {
  section: ProfileSection
  sub_field_suggestions: string[]
}

/** One row of the Active Patients caseload report. */
export interface ActivePatientRow {
  needs_psychiatric_review: boolean
  safety_risk: boolean
  custom_flag_active: boolean
  custom_flag_label: string | null

  patient_id: number
  mrn: string
  name: string
  age: number
  status: TreatmentStatus
  psychotropic_medications: boolean

  /**
   * Score cells. `*_stale` marks a last score older than 30 days (the
   * CTMS's asterisk); `*_single_score` means First and Last came from the
   * same contact (the CTMS grays First); `phq9_last_color` is the
   * confirmed red/yellow/green rule. GAD-7 and PCL-5 have no confirmed
   * color rule, so they deliberately have no color field.
   */
  phq9_first: number | null
  phq9_last: number | null
  phq9_stale: boolean | null
  phq9_single_score: boolean | null
  phq9_last_color: 'red' | 'yellow' | 'green' | null
  gad7_first: number | null
  gad7_last: number | null
  gad7_stale: boolean | null
  gad7_single_score: boolean | null
  pcl5_first: number | null
  pcl5_last: number | null
  pcl5_stale: boolean | null
  pcl5_single_score: boolean | null

  initial_assessment_date: string | null
  follow_up_date: string | null
  /** An ISO date, or the literal string "CONSIDER" while flagged. */
  psychiatric_consultation: string | null
  relapse_prevention_plan_date: string | null

  session_count: number
  weeks_since_initial_assessment: number | null
  minutes_this_month: number
}

export interface MeasureTrendPoint {
  score_date: string
  score_value: number
}

export interface MeasureTrend {
  condition: ConditionType
  is_primary: boolean
  measure_type: MeasureType
  baseline_score: number | null
  baseline_date: string | null
  latest_score: number | null
  latest_date: string | null
  is_response: boolean | null
  is_remission: boolean | null
  scores: MeasureTrendPoint[]
}

export interface ClinicalDashboard {
  patient_id: number
  mrn: string
  name: string
  age: number
  date_of_birth: string
  race_ethnicity: string[] | null
  payer: string
  program_eligibility: Record<string, unknown> | null
  consent_date: string
  enrollment_date: string
  deactivation_date: string | null

  needs_psychiatric_review: boolean
  safety_risk: boolean
  custom_flag_active: boolean
  custom_flag_label: string | null

  current_status: TreatmentStatus | null
  status_changed_date: string | null

  current_providers: {
    provider_id: number
    name: string
    role: ProviderRole
    phone: string | null
    email: string | null
    service_begin_date: string
  }[]
  current_clinics: {
    clinic_id: string
    is_primary: boolean
    service_begin_date: string
  }[]
  episodes: {
    episode_id: number
    start_date: string
    end_date: string | null
    end_reason: EndReason | null
    baseline_measure_type: MeasureType | null
    baseline_score: number | null
    baseline_date: string | null
  }[]
  symptom_scores: {
    episode_id: number
    measure_type: MeasureType
    score_value: number
    score_date: string
  }[]
  medications: {
    medication_id: number
    medication_key: string | null
    medication_name: string
    dose: string | null
    frequency: string | null
    is_current: boolean
    stop_reason: string | null
  }[]
  profile_entries: {
    profile_entry_id: number
    section: ProfileSection
    sub_field: string
    value: string
    context: string | null
    recorded_date: string
    recorded_by: string | null
  }[]
  measure_trends: MeasureTrend[]
}

export interface CaseloadStatisticsRow {
  group_type: string
  group_key: string
  group_label: string

  caseload_size: number
  patients_with_contact_count: number
  patients_with_contact_percentage: number
  avg_visits_per_patient: number
  avg_session_duration_minutes: number | null
  pct_contacts_with_completed_scale: number
  rpp_count: number
  rpp_percentage: number
  flagged_count: number
  flagged_percentage: number
  with_consultation_count: number
  with_consultation_percentage: number
  not_improving_without_consultation_count: number
  avg_psychiatric_case_reviews: number

  avg_phq9_first: number | null
  avg_phq9_last: number | null
  avg_gad7_first: number | null
  avg_gad7_last: number | null
  avg_pcl5_first: number | null
  avg_pcl5_last: number | null

  combined_response_count: number
  combined_response_denominator: number
  combined_response_percentage: number
  combined_remission_count: number
  combined_remission_denominator: number
  combined_remission_percentage: number

  depression_response_count: number
  depression_response_denominator: number
  depression_response_percentage: number
  depression_remission_count: number
  depression_remission_denominator: number
  depression_remission_percentage: number
  anxiety_response_count: number
  anxiety_response_denominator: number
  anxiety_response_percentage: number
  anxiety_remission_count: number
  anxiety_remission_denominator: number
  anxiety_remission_percentage: number
}

export interface QualityMetricsMonth {
  year: number
  month: number
  caseload_size: number
  caseload_reach: number | null
  engagement_count: number
  engagement_denominator: number
  engagement_percentage: number
  measures_completion_count: number
  measures_completion_denominator: number
  measures_completion_percentage: number
  depression_response_count: number
  depression_response_denominator: number
  depression_response_percentage: number
  anxiety_improvement_count: number
  anxiety_improvement_denominator: number
  anxiety_improvement_percentage: number
  ptsd_improvement_count: number
  ptsd_improvement_denominator: number
  ptsd_improvement_percentage: number
  pediatric_anxiety_improvement_count: number
  pediatric_anxiety_improvement_denominator: number
  pediatric_anxiety_improvement_percentage: number
  pediatric_depression_response_count: number
  pediatric_depression_response_denominator: number
  pediatric_depression_response_percentage: number
  pediatric_adhd_improvement_count: number
  pediatric_adhd_improvement_denominator: number
  pediatric_adhd_improvement_percentage: number
  psychiatric_case_review_count: number
  psychiatric_case_review_denominator: number
  psychiatric_case_review_percentage: number
}

export interface CompletedEpisodeStatistics {
  year: number
  total_completed_episodes: number
  avg_weeks_in_treatment: number | null
  avg_contacts_per_episode: number | null
  relapse_prevention_plan_count: number
  deactivation_reason_counts: Record<string, number>
  depression_response_count: number
  depression_response_denominator: number
  anxiety_improvement_count: number
  anxiety_improvement_denominator: number
  ptsd_improvement_count: number
  ptsd_improvement_denominator: number
}

export interface DRRClinicRow {
  clinic_id: string
  index_episode_count: number
  follow_up_phq9_count: number
  follow_up_phq9_percentage: number
  depression_remission_count: number
  depression_remission_percentage: number
  depression_response_count: number
  depression_response_percentage: number
}

export interface TimeTrackerPatientRow {
  patient_id: number
  mrn: string
  name: string
  months: { year: number; month: number; minutes: number }[]
  total_minutes: number
}
