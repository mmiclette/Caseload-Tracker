/**
 * Display formatting.
 *
 * Enum labels live here so the same value never gets two different labels
 * in two components — the frontend twin of the backend's
 * single-source-of-truth discipline.
 */

import type {
  ConditionType,
  ContactLocation,
  ContactType,
  EndReason,
  MedicationConfirmation,
  ProviderRole,
  TreatmentStatus,
} from '../api/types'

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

/**
 * ISO date (YYYY-MM-DD) → "M/D/YY", the CTMS's own compact table format.
 * Parsed by hand rather than through `new Date(iso)`, which would treat a
 * bare date as UTC midnight and shift it a day in western timezones.
 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return iso
  return `${m}/${d}/${String(y).slice(2)}`
}

/** ISO date → "Mar 12, 2026", for headers and detail views. */
export function formatDateLong(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return iso
  return `${MONTHS[m - 1]} ${d}, ${y}`
}

export function formatMonth(year: number, month: number): string {
  return `${MONTHS[month - 1]} ${year}`
}

/** Percentage with a single decimal, or an em dash when there's no denominator. */
export function formatRate(count: number, denominator: number, percentage: number): string {
  if (denominator === 0) return '—'
  return `${count}/${denominator} (${percentage}%)`
}

export function formatNumber(value: number | null | undefined, suffix = ''): string {
  if (value === null || value === undefined) return '—'
  return `${value}${suffix}`
}

export const TREATMENT_STATUS_LABELS: Record<TreatmentStatus, string> = {
  active_treatment: 'Active treatment',
  relapse_prevention_plan: 'Relapse prevention',
  deactivated: 'Deactivated',
}

/** The CTMS's compact status codes for dense table cells. */
export const TREATMENT_STATUS_SHORT: Record<TreatmentStatus, string> = {
  active_treatment: 'T',
  relapse_prevention_plan: 'RPP',
  deactivated: 'D',
}

export const CONTACT_TYPE_LABELS: Record<ContactType, string> = {
  initial_assessment: 'Initial assessment',
  follow_up: 'Follow-up',
  relapse_prevention_plan: 'Relapse prevention plan',
  contact_attempt: 'Contact attempt',
  care_team_collaboration: 'Care team collaboration',
}

export const CONTACT_LOCATION_LABELS: Record<ContactLocation, string> = {
  phone: 'By phone',
  in_clinic: 'In clinic',
  virtual: 'Virtual',
}

export const CONDITION_LABELS: Record<ConditionType, string> = {
  depression: 'Depression',
  anxiety: 'Anxiety',
  ptsd: 'PTSD',
  adhd: 'ADHD',
  substance_use: 'Substance use',
}

export const PROVIDER_ROLE_LABELS: Record<ProviderRole, string> = {
  care_manager: 'Care Manager',
  primary_care_provider: 'Primary Care Provider',
  psychiatric_consultant: 'Psychiatric Consultant',
  clinic_supervisor: 'Clinic Supervisor',
  data_analyst: 'Data Analyst',
}

export const END_REASON_LABELS: Record<EndReason, string> = {
  achieved_goals: 'Achieved goals',
  not_engaged: 'Not engaged',
  patient_choice: 'Patient choice',
  patient_no_longer_available: 'No longer available',
  patient_died: 'Patient died',
  patient_died_by_suicide: 'Died by suicide',
  other: 'Other',
}

export const MEDICATION_CONFIRMATION_LABELS: Record<MedicationConfirmation, string> = {
  confirmed_with_patient: 'Confirmed with the patient',
  confirmed_in_medical_record: "Confirmed in the patient's medical record",
  deferred: 'Deferred',
}

/** "not_recorded" → "Not recorded", for keys with no fixed label map. */
export function humanize(key: string): string {
  const spaced = key.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** Minutes dropdown, in the CTMS's confirmed 5-minute increments. */
export const DURATION_OPTIONS = Array.from({ length: 24 }, (_, i) => (i + 1) * 5)
