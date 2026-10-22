import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { useApi } from '../api/hooks'
import type { EndReason, Episode, Patient } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { END_REASON_LABELS, formatDateLong } from '../lib/format'
import './RecordContact.css'
import './EnrollPatient.css'

/**
 * Deactivation — closing a patient's episode of care.
 *
 * The CTMS calls this a contact type ("New Contact ▸ Deactivation") but it
 * isn't one in this data model: it closes the episode. Setting end_date is
 * what the server treats as deactivation, and EpisodeService cascades from
 * there — transitioning treatment status to deactivated and dismissing any
 * pending appointment reminder. This form deliberately does not do those
 * three things itself; it makes one PATCH and lets the cascade run, which
 * is exactly why the cascade lives server-side.
 *
 * The end reason is a deactivation reason, never a clinical outcome.
 * Remission and response are computed from scores and reported separately,
 * so "achieved goals" here is a statement about why treatment stopped, not
 * a claim that the patient improved.
 */

const END_REASONS: EndReason[] = [
  'achieved_goals',
  'patient_choice',
  'not_engaged',
  'patient_no_longer_available',
  'patient_died',
  'patient_died_by_suicide',
  'other',
]

function today(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export function DeactivatePatient() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const navigate = useNavigate()

  const patient = useApi<Patient>(`/patients/${id}`)
  const episodes = useApi<Episode[]>('/episodes', { patient_id: id })

  const [endDate, setEndDate] = useState(today())
  const [endReason, setEndReason] = useState<EndReason | ''>('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const openEpisode = useMemo(
    () => (episodes.data ?? []).find((e) => e.end_date === null) ?? null,
    [episodes.data],
  )

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!openEpisode) return
    setError(null)
    setSaving(true)
    try {
      // One call. EpisodeService.update_episode cascades the treatment
      // status to deactivated and dismisses the pending reminder.
      await api.patch(`/episodes/${openEpisode.episode_id}`, {
        end_date: endDate,
        end_reason: endReason || null,
      })
      // The patient's own registry-membership window, separate from the
      // episode's — this is what the Inactive Patients list reads.
      await api.patch(`/patients/${id}`, { deactivation_date: endDate })
      navigate('/patients/inactive')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not deactivate this patient.')
    } finally {
      setSaving(false)
    }
  }

  if (patient.loading || episodes.loading) {
    return (
      <div>
        <PageHeader title="Deactivation" />
        <div className="card">
          <div className="table-loading">Loading patient…</div>
        </div>
      </div>
    )
  }

  if (patient.error || !patient.data) {
    return (
      <div>
        <PageHeader title="Deactivation" />
        <div className="error-banner" role="alert">
          {patient.error ?? 'Patient not found.'}
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit}>
      <PageHeader
        title="Deactivation"
        subtitle={
          <>
            {patient.data.name} · MRN {patient.data.mrn}
          </>
        }
        meta={
          openEpisode ? (
            <div>Episode opened {formatDateLong(openEpisode.start_date)}</div>
          ) : (
            <div>No open episode</div>
          )
        }
      />

      {error && (
        <div className="error-banner contact-form__error" role="alert">
          {error}
        </div>
      )}

      {!openEpisode ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state__title">This patient has no open episode</div>
            They are already off the active caseload. Re-enroll them from Inactive Patients to open a
            new episode.
          </div>
        </div>
      ) : (
        <div className="stack">
          <section className="card">
            <div className="card__header">
              <h2 className="card__title">Close the episode of care</h2>
            </div>
            <div className="card__body stack">
              <div className="deactivate__warning">
                Saving this closes the current episode, sets the patient's treatment status to
                deactivated, removes them from the active caseload, and clears their pending
                appointment reminder. Their full history is kept, and they can be re-enrolled at any
                time from Inactive Patients.
              </div>

              <div className="contact-form__grid">
                <div className="field">
                  <label className="field__label" htmlFor="deactivate-date">
                    Date of deactivation <span className="field__required">*</span>
                  </label>
                  <div className="row">
                    <input
                      id="deactivate-date"
                      className="input"
                      type="date"
                      required
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                    />
                    <button
                      type="button"
                      className="btn btn--secondary btn--sm"
                      onClick={() => setEndDate(today())}
                    >
                      Today
                    </button>
                  </div>
                </div>
                <div className="field">
                  <label className="field__label" htmlFor="deactivate-reason">
                    Reason
                  </label>
                  <select
                    id="deactivate-reason"
                    className="select"
                    value={endReason}
                    onChange={(e) => setEndReason(e.target.value as EndReason | '')}
                  >
                    <option value="">Not recorded</option>
                    {END_REASONS.map((reason) => (
                      <option key={reason} value={reason}>
                        {END_REASON_LABELS[reason]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <p className="enroll__note">
                This is a deactivation reason, not a clinical outcome — remission and response are
                computed from symptom scores and reported separately. Leaving it unrecorded is
                allowed, and Completed Episode Statistics counts those episodes in a “not recorded”
                bucket rather than hiding them.
              </p>
            </div>
          </section>

          <div className="contact-form__actions">
            <button type="submit" className="btn btn--cta" disabled={saving}>
              {saving ? 'Deactivating…' : 'Deactivate patient'}
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => navigate(`/patients/${id}`)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </form>
  )
}
