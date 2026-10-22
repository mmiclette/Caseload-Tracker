import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { useApi } from '../api/hooks'
import type { Consultation, Contact, Patient, Provider } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { DURATION_OPTIONS, formatDateLong } from '../lib/format'
import './RecordContact.css'

/**
 * The Psychiatric Consultation Note.
 *
 * Follows the CTMS's own layout: date of contact, a read-only replay of the
 * care manager's comments from the flagging contact, the consultant's
 * findings, and the session footer. Its location in the CTMS is fixed
 * ("case review with CM") and a Consultation has no location column, so
 * there's no location control here.
 *
 * Saving this clears the patient's yellow review flag — unless "flag for
 * next review" is checked, which immediately re-sets it. That cascade lives
 * in ConsultationService, not here.
 */
export function RecordConsultation() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const navigate = useNavigate()

  const patient = useApi<Patient>(`/patients/${id}`)
  const contacts = useApi<Contact[]>('/contacts', { patient_id: id })
  const providers = useApi<Provider[]>('/providers', { limit: 200 })

  const [consultationDate, setConsultationDate] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  })
  const [providerId, setProviderId] = useState('')
  const [durationMinutes, setDurationMinutes] = useState('')
  const [notes, setNotes] = useState('')
  const [forwarded, setForwarded] = useState(false)
  const [flagNext, setFlagNext] = useState(false)
  const [flagReason, setFlagReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  /** The most recent contact that asked for a consultant review. */
  const flaggingContact = useMemo(
    () =>
      [...(contacts.data ?? [])]
        .filter((c) => c.discuss_with_psychiatric_consultant)
        .sort((a, b) => b.contact_date.localeCompare(a.contact_date))[0] ?? null,
    [contacts.data],
  )

  const psychiatricConsultants = (providers.data ?? []).filter(
    (p) => p.role === 'psychiatric_consultant',
  )

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSaving(true)
    try {
      await api.post<Consultation>('/consultations', {
        patient_id: id,
        provider_id: providerId ? Number(providerId) : null,
        consultation_date: consultationDate,
        duration_minutes: durationMinutes ? Number(durationMinutes) : null,
        recommendations_forwarded: forwarded,
        flagged_for_next_review: flagNext,
        flag_reason: flagNext && flagReason ? flagReason : null,
        notes: notes || null,
      })
      navigate(`/patients/${id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save this consultation.')
    } finally {
      setSaving(false)
    }
  }

  if (patient.loading) {
    return (
      <div>
        <PageHeader title="Psychiatric Consultation Note" />
        <div className="card">
          <div className="table-loading">Loading patient…</div>
        </div>
      </div>
    )
  }

  if (patient.error || !patient.data) {
    return (
      <div>
        <PageHeader title="Psychiatric Consultation Note" />
        <div className="error-banner" role="alert">
          {patient.error ?? 'Patient not found.'}
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit}>
      <PageHeader
        title="Psychiatric Consultation Note"
        subtitle={
          <>
            {patient.data.name} · MRN {patient.data.mrn} · Age {patient.data.age}
          </>
        }
        meta={
          patient.data.needs_psychiatric_review ? (
            <div>Flagged for review</div>
          ) : (
            <div>Not currently flagged</div>
          )
        }
      />

      {error && (
        <div className="error-banner contact-form__error" role="alert">
          {error}
        </div>
      )}

      <div className="stack">
        <section className="card">
          <div className="card__header">
            <h2 className="card__title">Comments from care manager</h2>
            {flaggingContact && (
              <span className="text-xs muted">
                From the contact on {formatDateLong(flaggingContact.contact_date)}
              </span>
            )}
          </div>
          <div className="card__body">
            {flaggingContact?.notes_for_consultant ? (
              <blockquote className="consult__quote">
                {flaggingContact.notes_for_consultant}
              </blockquote>
            ) : (
              <p className="muted text-xs">
                No care manager comments on file. The care manager records these by checking
                “discuss with psychiatric consultant” on a contact.
              </p>
            )}
          </div>
        </section>

        <section className="card">
          <div className="card__header">
            <h2 className="card__title">Consultation</h2>
          </div>
          <div className="card__body stack">
            <div className="contact-form__grid">
              <div className="field">
                <label className="field__label" htmlFor="consult-date">
                  Date of contact <span className="field__required">*</span>
                </label>
                <input
                  id="consult-date"
                  className="input"
                  type="date"
                  required
                  value={consultationDate}
                  onChange={(e) => setConsultationDate(e.target.value)}
                />
              </div>
              <div className="field">
                <label className="field__label" htmlFor="consult-provider">
                  Psychiatric consultant
                </label>
                <select
                  id="consult-provider"
                  className="select"
                  value={providerId}
                  onChange={(e) => setProviderId(e.target.value)}
                >
                  <option value="">—</option>
                  {psychiatricConsultants.map((p) => (
                    <option key={p.provider_id} value={p.provider_id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="field">
              <label className="field__label" htmlFor="consult-notes">
                Findings and recommendations
              </label>
              <textarea
                id="consult-notes"
                className="textarea contact-form__note"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>

            <label className="contact-form__checkbox">
              <input
                type="checkbox"
                checked={forwarded}
                onChange={(e) => setForwarded(e.target.checked)}
              />
              Recommendations forwarded to the primary care provider
            </label>

            <label className="contact-form__checkbox">
              <input
                type="checkbox"
                checked={flagNext}
                onChange={(e) => setFlagNext(e.target.checked)}
              />
              Flag this patient for the next review
            </label>
            {flagNext ? (
              <div className="field">
                <label className="field__label" htmlFor="flag-reason">
                  Reason to review again
                </label>
                <input
                  id="flag-reason"
                  className="input"
                  value={flagReason}
                  onChange={(e) => setFlagReason(e.target.value)}
                />
              </div>
            ) : (
              patient.data.needs_psychiatric_review && (
                <p className="contact-form__hint">
                  Saving will clear this patient’s review flag.
                </p>
              )
            )}
          </div>
        </section>

        <section className="card">
          <div className="card__body contact-form__footer">
            <span>This session was a case review with the care manager and took</span>
            <select
              className="select contact-form__inline-select contact-form__inline-select--narrow"
              aria-label="Duration in minutes"
              value={durationMinutes}
              onChange={(e) => setDurationMinutes(e.target.value)}
            >
              <option value="">—</option>
              {DURATION_OPTIONS.map((minutes) => (
                <option key={minutes} value={minutes}>
                  {minutes}
                </option>
              ))}
            </select>
            <span>minutes</span>
          </div>
        </section>

        <div className="contact-form__actions">
          <button type="submit" className="btn btn--cta" disabled={saving}>
            {saving ? 'Saving…' : 'Save consultation'}
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
    </form>
  )
}
