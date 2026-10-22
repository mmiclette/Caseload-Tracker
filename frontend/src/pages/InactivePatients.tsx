import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { useApi } from '../api/hooks'
import type { ActivePatientRow, ConditionType, Episode, Patient } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { SortHeader, useSort } from '../components/SortableHeader'
import { CONDITION_LABELS, END_REASON_LABELS, formatDate } from '../lib/format'
import '../components/DataTable.css'
import './EnrollPatient.css'

/**
 * Inactive Patients — the CTMS's second caseload list.
 *
 * There's no inactive-patients endpoint, so this derives the list: every
 * patient who is NOT on the Active Patients report. That's exactly the
 * report's own exclusion rule (no open episode, or a deactivated treatment
 * status), so the two lists partition the roster without needing the
 * backend to answer the same question twice.
 *
 * Re-enrollment opens a NEW episode rather than reopening the old one,
 * which is the AIMS rule the data model is built around: a patient
 * returning after a gap starts a new episode with a new baseline. Because
 * EpisodeService sets an active treatment status on creation, opening the
 * episode is all it takes to move the patient back onto the caseload.
 */

const CONDITIONS: ConditionType[] = ['depression', 'anxiety', 'ptsd', 'adhd', 'substance_use']

type SortKey = 'name' | 'mrn' | 'deactivated' | 'enrolled'

export function InactivePatients() {
  const patients = useApi<Patient[]>('/patients', { limit: 500 })
  const active = useApi<ActivePatientRow[]>('/reports/active-patients')
  const [reEnrolling, setReEnrolling] = useState<Patient | null>(null)

  const inactive = useMemo(() => {
    if (!patients.data || !active.data) return []
    const activeIds = new Set(active.data.map((r) => r.patient_id))
    return patients.data.filter((p) => !activeIds.has(p.patient_id))
  }, [patients.data, active.data])

  const { sorted, sort, toggle } = useSort<Patient, SortKey>(
    inactive,
    {
      name: (p) => p.name,
      mrn: (p) => p.mrn,
      deactivated: (p) => p.deactivation_date,
      enrolled: (p) => p.enrollment_date,
    },
    { key: 'deactivated', direction: 'desc' },
  )

  const loading = patients.loading || active.loading
  const error = patients.error ?? active.error

  return (
    <div>
      <PageHeader
        title="Inactive Patients"
        subtitle="Patients who have completed an episode of care"
        meta={
          <div>
            <strong>{inactive.length}</strong> inactive
          </div>
        }
      />

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      <div className="card">
        <div className="table-wrap">
          {loading ? (
            <div className="table-loading">Loading…</div>
          ) : inactive.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__title">No inactive patients</div>
              Patients appear here after their episode of care is closed. They keep their full
              history and can be re-enrolled at any time.
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <SortHeader label="Patient ID" sortKey="mrn" sort={sort} onSort={toggle} />
                  <th>MRN</th>
                  <SortHeader label="Name" sortKey="name" sort={sort} onSort={toggle} />
                  <th className="is-numeric">Age</th>
                  <th>Payer</th>
                  <SortHeader label="Enrolled" sortKey="enrolled" sort={sort} onSort={toggle} />
                  <SortHeader
                    label="Deactivated"
                    sortKey="deactivated"
                    sort={sort}
                    onSort={toggle}
                  />
                  <th>Last episode outcome</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {sorted.map((patient) => (
                  <InactiveRow
                    key={patient.patient_id}
                    patient={patient}
                    onReEnroll={() => setReEnrolling(patient)}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
        {inactive.length > 0 && (
          <div className="data-table__footer">
            <span>
              {inactive.length} inactive {inactive.length === 1 ? 'patient' : 'patients'}
            </span>
            <span>Re-enrolling opens a new episode with a new baseline</span>
          </div>
        )}
      </div>

      {reEnrolling && (
        <ReEnrollDialog
          patient={reEnrolling}
          onClose={() => setReEnrolling(null)}
          onDone={() => {
            setReEnrolling(null)
            patients.reload()
            active.reload()
          }}
        />
      )}
    </div>
  )
}

function InactiveRow({ patient, onReEnroll }: { patient: Patient; onReEnroll: () => void }) {
  const episodes = useApi<Episode[]>('/episodes', { patient_id: patient.patient_id })
  const lastClosed = useMemo(() => {
    const closed = (episodes.data ?? []).filter((e) => e.end_date !== null)
    return closed.sort((a, b) => (b.end_date ?? '').localeCompare(a.end_date ?? ''))[0] ?? null
  }, [episodes.data])

  return (
    <tr>
      <td className="tabular muted">{String(patient.patient_id).padStart(8, '0')}</td>
      <td className="tabular">{patient.mrn}</td>
      <td>
        <Link to={`/patients/${patient.patient_id}`}>{patient.name}</Link>
      </td>
      <td className="is-numeric">{patient.age}</td>
      <td>{patient.payer}</td>
      <td className="nowrap">{formatDate(patient.enrollment_date)}</td>
      <td className="nowrap">
        {patient.deactivation_date
          ? formatDate(patient.deactivation_date)
          : lastClosed?.end_date
            ? formatDate(lastClosed.end_date)
            : '—'}
      </td>
      <td>
        {lastClosed?.end_reason ? (
          END_REASON_LABELS[lastClosed.end_reason]
        ) : lastClosed ? (
          <span className="muted">Not recorded</span>
        ) : (
          <span className="muted">No closed episode</span>
        )}
      </td>
      <td className="is-center">
        <button type="button" className="btn btn--secondary btn--sm" onClick={onReEnroll}>
          Re-enroll
        </button>
      </td>
    </tr>
  )
}

function ReEnrollDialog({
  patient,
  onClose,
  onDone,
}: {
  patient: Patient
  onClose: () => void
  onDone: () => void
}) {
  const [startDate, setStartDate] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  })
  const [primary, setPrimary] = useState<ConditionType | ''>('')
  const [secondary, setSecondary] = useState<ConditionType | ''>('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.post<Episode>('/episodes', {
        patient_id: patient.patient_id,
        start_date: startDate,
        primary_diagnosis: primary || null,
        secondary_diagnosis: secondary || null,
      })
      // Clear the deactivation date so the roster reflects an active patient.
      if (patient.deactivation_date) {
        await api.patch(`/patients/${patient.patient_id}`, { deactivation_date: null })
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not re-enroll this patient.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label={`Re-enroll ${patient.name}`}>
      <form className="modal__panel card" onSubmit={submit}>
        <div className="card__header">
          <h2 className="card__title">Re-enroll {patient.name}</h2>
        </div>
        <div className="card__body stack">
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
          <p className="enroll__note">
            This opens a new episode of care. Progress will be measured from a new baseline — the
            first score recorded in this episode — leaving the previous episode's history intact.
          </p>
          <div className="field">
            <label className="field__label" htmlFor="reenroll-date">
              Episode start date <span className="field__required">*</span>
            </label>
            <input
              id="reenroll-date"
              className="input"
              type="date"
              required
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="reenroll-primary">
              Primary diagnosis <span className="field__required">*</span>
            </label>
            <select
              id="reenroll-primary"
              className="select"
              required
              value={primary}
              onChange={(e) => setPrimary(e.target.value as ConditionType | '')}
            >
              <option value="">Select…</option>
              {CONDITIONS.map((c) => (
                <option key={c} value={c}>
                  {CONDITION_LABELS[c]}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field__label" htmlFor="reenroll-secondary">
              Secondary diagnosis
            </label>
            <select
              id="reenroll-secondary"
              className="select"
              value={secondary}
              onChange={(e) => setSecondary(e.target.value as ConditionType | '')}
            >
              <option value="">None</option>
              {CONDITIONS.filter((c) => c !== primary).map((c) => (
                <option key={c} value={c}>
                  {CONDITION_LABELS[c]}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="modal__actions">
          <button type="submit" className="btn btn--cta" disabled={saving}>
            {saving ? 'Re-enrolling…' : 'Open new episode'}
          </button>
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
