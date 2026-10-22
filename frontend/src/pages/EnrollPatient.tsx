import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { useApi } from '../api/hooks'
import type { ConditionType, Episode, Patient, Provider } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { CONDITION_LABELS } from '../lib/format'
import './RecordContact.css'
import './EnrollPatient.css'

/**
 * Patient Enrollment.
 *
 * Follows the CTMS's own form — Program Information then Demographic
 * Information, with Care Manager required and Psychiatric Consultant
 * optional — but enrolling is four API calls, not one: the patient, their
 * first episode of care, the care team assignment, and the clinic
 * assignment. They're issued in that order because each later call needs
 * the patient_id, and a failure part-way through is reported honestly
 * rather than rolled back, since the API has no transactional enrollment
 * endpoint. If this becomes a real problem, the fix is a server-side
 * enrollment service, not client-side compensation logic.
 *
 * Three fields the CTMS doesn't show on this screen are required here
 * because the data model requires them: payer, consent date (per AIMS
 * guidance a patient enters the registry after consenting), and a primary
 * diagnosis — which is what pins the patient's outcome reporting to a
 * measure, so collecting it at enrollment avoids episodes that can never
 * report.
 */

const RACE_ETHNICITY_OPTIONS: { value: string; label: string }[] = [
  { value: 'american_indian_or_alaska_native', label: 'American Indian or Alaska Native' },
  { value: 'asian', label: 'Asian' },
  { value: 'black_or_african_american', label: 'Black or African American' },
  { value: 'hispanic_or_latino', label: 'Hispanic or Latino' },
  { value: 'middle_eastern_or_north_african', label: 'Middle Eastern or North African' },
  { value: 'native_hawaiian_or_pacific_islander', label: 'Native Hawaiian or Pacific Islander' },
  { value: 'white', label: 'White' },
  { value: 'patient_declined', label: 'Patient declined' },
]

const CONDITIONS: ConditionType[] = ['depression', 'anxiety', 'ptsd', 'adhd', 'substance_use']

function today(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export function EnrollPatient() {
  const navigate = useNavigate()
  const providers = useApi<Provider[]>('/providers', { limit: 200 })

  const [clinicId, setClinicId] = useState('')
  const [enrollmentDate, setEnrollmentDate] = useState(today())
  const [consentDate, setConsentDate] = useState(today())
  const [mrn, setMrn] = useState('')
  const [payer, setPayer] = useState('')
  const [careManagerId, setCareManagerId] = useState('')
  const [consultantId, setConsultantId] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [dateOfBirth, setDateOfBirth] = useState('')
  const [raceEthnicity, setRaceEthnicity] = useState<string[]>([])
  const [primaryDiagnosis, setPrimaryDiagnosis] = useState<ConditionType | ''>('')
  const [secondaryDiagnosis, setSecondaryDiagnosis] = useState<ConditionType | ''>('')

  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const careManagers = (providers.data ?? []).filter((p) => p.role === 'care_manager')
  const consultants = (providers.data ?? []).filter((p) => p.role === 'psychiatric_consultant')

  function toggleRace(value: string) {
    setRaceEthnicity((current) =>
      current.includes(value) ? current.filter((v) => v !== value) : [...current, value],
    )
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)

    if (secondaryDiagnosis && secondaryDiagnosis === primaryDiagnosis) {
      setError('The secondary diagnosis must differ from the primary diagnosis.')
      return
    }
    if (secondaryDiagnosis && !primaryDiagnosis) {
      setError('A secondary diagnosis requires a primary diagnosis.')
      return
    }

    setSaving(true)
    let patient: Patient | null = null
    try {
      setProgress('Creating patient…')
      patient = await api.post<Patient>('/patients', {
        mrn: mrn.trim(),
        name: `${firstName.trim()} ${lastName.trim()}`.trim(),
        payer: payer.trim(),
        date_of_birth: dateOfBirth,
        consent_date: consentDate,
        enrollment_date: enrollmentDate,
        race_ethnicity: raceEthnicity.length > 0 ? raceEthnicity : null,
        program_eligibility: null,
      })

      setProgress('Opening episode of care…')
      await api.post<Episode>('/episodes', {
        patient_id: patient.patient_id,
        start_date: enrollmentDate,
        primary_diagnosis: primaryDiagnosis || null,
        secondary_diagnosis: secondaryDiagnosis || null,
      })

      setProgress('Assigning care team…')
      await api.post('/care-team-assignments', {
        patient_id: patient.patient_id,
        provider_id: Number(careManagerId),
        role: 'care_manager',
        service_begin_date: enrollmentDate,
      })
      if (consultantId) {
        await api.post('/care-team-assignments', {
          patient_id: patient.patient_id,
          provider_id: Number(consultantId),
          role: 'psychiatric_consultant',
          service_begin_date: enrollmentDate,
        })
      }

      setProgress('Assigning clinic…')
      await api.post('/clinic-assignments', {
        patient_id: patient.patient_id,
        clinic_id: clinicId.trim(),
        is_primary: true,
        service_begin_date: enrollmentDate,
      })

      navigate(`/patients/${patient.patient_id}`)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not complete enrollment.'
      setError(
        patient
          ? `${message} The patient record was created (ID ${patient.patient_id}) but enrollment did not finish — open the patient to complete it.`
          : message,
      )
      setProgress(null)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <PageHeader
        title="Patient Enrollment"
        subtitle="Enroll a patient into the collaborative care program"
      />

      {error && (
        <div className="error-banner contact-form__error" role="alert">
          {error}
        </div>
      )}

      <div className="stack">
        <section className="card">
          <div className="card__header">
            <h2 className="card__title">Program information</h2>
          </div>
          <div className="card__body contact-form__grid">
            <div className="field">
              <label className="field__label" htmlFor="enroll-clinic">
                Clinic <span className="field__required">*</span>
              </label>
              <input
                id="enroll-clinic"
                className="input"
                required
                value={clinicId}
                onChange={(e) => setClinicId(e.target.value)}
                placeholder="e.g. northside"
              />
            </div>
            <div className="field">
              <label className="field__label" htmlFor="enroll-mrn">
                MRN <span className="field__required">*</span>
              </label>
              <input
                id="enroll-mrn"
                className="input"
                required
                value={mrn}
                onChange={(e) => setMrn(e.target.value)}
              />
            </div>
            <div className="field">
              <label className="field__label" htmlFor="enroll-consent">
                Consent date <span className="field__required">*</span>
              </label>
              <input
                id="enroll-consent"
                className="input"
                type="date"
                required
                value={consentDate}
                onChange={(e) => setConsentDate(e.target.value)}
              />
            </div>
            <div className="field">
              <label className="field__label" htmlFor="enroll-date">
                Enrollment date <span className="field__required">*</span>
              </label>
              <input
                id="enroll-date"
                className="input"
                type="date"
                required
                value={enrollmentDate}
                onChange={(e) => setEnrollmentDate(e.target.value)}
              />
            </div>
            <div className="field">
              <label className="field__label" htmlFor="enroll-payer">
                Insurance / payer <span className="field__required">*</span>
              </label>
              <input
                id="enroll-payer"
                className="input"
                required
                value={payer}
                onChange={(e) => setPayer(e.target.value)}
                placeholder="e.g. Medicaid"
              />
            </div>
            <div className="field">
              <label className="field__label" htmlFor="enroll-cm">
                Care manager <span className="field__required">*</span>
              </label>
              <select
                id="enroll-cm"
                className="select"
                required
                value={careManagerId}
                onChange={(e) => setCareManagerId(e.target.value)}
              >
                <option value="">Select…</option>
                {careManagers.map((p) => (
                  <option key={p.provider_id} value={p.provider_id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field__label" htmlFor="enroll-consultant">
                Psychiatric consultant
              </label>
              <select
                id="enroll-consultant"
                className="select"
                value={consultantId}
                onChange={(e) => setConsultantId(e.target.value)}
              >
                <option value="">None yet</option>
                {consultants.map((p) => (
                  <option key={p.provider_id} value={p.provider_id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="card__header">
            <h2 className="card__title">Demographic information</h2>
          </div>
          <div className="card__body stack">
            <div className="contact-form__grid">
              <div className="field">
                <label className="field__label" htmlFor="enroll-first">
                  First name <span className="field__required">*</span>
                </label>
                <input
                  id="enroll-first"
                  className="input"
                  required
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                />
              </div>
              <div className="field">
                <label className="field__label" htmlFor="enroll-last">
                  Last name <span className="field__required">*</span>
                </label>
                <input
                  id="enroll-last"
                  className="input"
                  required
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                />
              </div>
              <div className="field">
                <label className="field__label" htmlFor="enroll-dob">
                  Date of birth <span className="field__required">*</span>
                </label>
                <input
                  id="enroll-dob"
                  className="input"
                  type="date"
                  required
                  value={dateOfBirth}
                  onChange={(e) => setDateOfBirth(e.target.value)}
                />
              </div>
            </div>

            <div className="field">
              <span className="field__label">Race / ethnicity — select all that apply</span>
              <div className="enroll__checkbox-grid">
                {RACE_ETHNICITY_OPTIONS.map((option) => (
                  <label key={option.value} className="contact-form__checkbox">
                    <input
                      type="checkbox"
                      checked={raceEthnicity.includes(option.value)}
                      onChange={() => toggleRace(option.value)}
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="card">
          <div className="card__header">
            <h2 className="card__title">Episode of care</h2>
            <span className="text-xs muted">Opens with the enrollment date</span>
          </div>
          <div className="card__body stack">
            <div className="contact-form__grid">
              <div className="field">
                <label className="field__label" htmlFor="enroll-primary">
                  Primary diagnosis <span className="field__required">*</span>
                </label>
                <select
                  id="enroll-primary"
                  className="select"
                  required
                  value={primaryDiagnosis}
                  onChange={(e) => setPrimaryDiagnosis(e.target.value as ConditionType | '')}
                >
                  <option value="">Select…</option>
                  {CONDITIONS.map((condition) => (
                    <option key={condition} value={condition}>
                      {CONDITION_LABELS[condition]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="field__label" htmlFor="enroll-secondary">
                  Secondary diagnosis
                </label>
                <select
                  id="enroll-secondary"
                  className="select"
                  value={secondaryDiagnosis}
                  onChange={(e) => setSecondaryDiagnosis(e.target.value as ConditionType | '')}
                >
                  <option value="">None</option>
                  {CONDITIONS.filter((c) => c !== primaryDiagnosis).map((condition) => (
                    <option key={condition} value={condition}>
                      {CONDITION_LABELS[condition]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p className="enroll__note">
              The primary diagnosis determines which measure this patient's response and remission
              rates are tracked on — depression on the PHQ-9, anxiety on the GAD-7. The secondary
              diagnosis gets its own trend graph but stays out of the headline rates.
            </p>
          </div>
        </section>

        <div className="contact-form__actions">
          <button type="submit" className="btn btn--cta" disabled={saving}>
            {saving ? (progress ?? 'Enrolling…') : 'Enroll patient'}
          </button>
          <button type="button" className="btn btn--secondary" onClick={() => navigate('/patients')}>
            Cancel
          </button>
        </div>
      </div>
    </form>
  )
}
