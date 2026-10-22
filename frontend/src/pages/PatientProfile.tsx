import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { useApi } from '../api/hooks'
import type { Patient, ProfileEntry, ProfileSection, ProfileSectionDefinition } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { formatDate, humanize } from '../lib/format'
import '../components/DataTable.css'
import './RecordContact.css'
import './PatientProfile.css'

/**
 * The patient profile's free-form sections.
 *
 * The interaction is the one from the 2026-08 design: click a sub-field, add
 * a value. Each entry carries a clinical date (defaulting to today) and
 * optional context.
 *
 * The table is append-only and there are no edit or delete controls here
 * because the API has no such routes — by design. A changed circumstance,
 * or a correction, is a new entry that supersedes the old one at display
 * time, which is also what gives these rows their audit trail. The UI makes
 * that explicit rather than leaving a user hunting for an edit button.
 *
 * Two guardrails worth knowing: Current Medications offers only
 * allergies/intolerances here (the medications themselves are real
 * Medication rows), and Safety & Risk entries document risk without
 * touching the red safety flag — that flag stays the single alerting
 * signal.
 */

const SECTION_TITLES: Record<ProfileSection, string> = {
  behavioral_health: 'Behavioral Health',
  current_medications: 'Current Medications',
  medical_profile: 'Medical Profile',
  safety_and_risk: 'Safety & Risk',
  substance_use: 'Substance Use',
  social_environmental: 'Social & Environmental',
}

const SECTION_NOTES: Partial<Record<ProfileSection, string>> = {
  current_medications:
    'Allergies and intolerances only — medications themselves live on the medications screen.',
  safety_and_risk:
    'These entries document risk factors. They never set or clear the red safety flag, which stays the single alerting signal.',
  behavioral_health:
    'Diagnoses and symptom severity are deliberately absent: the treated diagnoses live on the episode, and severity is the symptom score.',
}

function today(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export function PatientProfile() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const patient = useApi<Patient>(`/patients/${id}`)
  const sections = useApi<ProfileSectionDefinition[]>('/profile-entries/sections')
  const entries = useApi<ProfileEntry[]>('/profile-entries', { patient_id: id })
  const [adding, setAdding] = useState<{ section: ProfileSection; subField: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  /** section → sub_field → entries, newest first (the API already orders them). */
  const grouped = useMemo(() => {
    const bySection = new Map<string, Map<string, ProfileEntry[]>>()
    for (const entry of entries.data ?? []) {
      if (!bySection.has(entry.section)) bySection.set(entry.section, new Map())
      const fields = bySection.get(entry.section)!
      if (!fields.has(entry.sub_field)) fields.set(entry.sub_field, [])
      fields.get(entry.sub_field)!.push(entry)
    }
    return bySection
  }, [entries.data])

  return (
    <div>
      <PageHeader
        title="Patient Profile"
        subtitle={
          patient.data ? (
            <>
              {patient.data.name} · MRN {patient.data.mrn}
            </>
          ) : undefined
        }
        actions={
          <Link className="btn btn--secondary" to={`/patients/${id}`}>
            Back to dashboard
          </Link>
        }
      />

      {error && (
        <div className="error-banner contact-form__error" role="alert">
          {error}
        </div>
      )}

      <div className="profile__intro">
        Entries are append-only: adding a value supersedes the previous one for that field and keeps
        the earlier entry as history. Nothing here is edited or deleted.
      </div>

      <div className="stack">
        {sections.loading ? (
          <div className="card">
            <div className="table-loading">Loading sections…</div>
          </div>
        ) : (
          (sections.data ?? []).map((definition) => {
            const fields = grouped.get(definition.section)
            const recordedFields = [...(fields?.keys() ?? [])]
            const suggestions = definition.sub_field_suggestions.filter(
              (s) => !recordedFields.includes(s),
            )
            return (
              <section className="card" key={definition.section}>
                <div className="card__header">
                  <h2 className="card__title">{SECTION_TITLES[definition.section]}</h2>
                  <span className="text-xs muted">
                    {recordedFields.length} recorded
                  </span>
                </div>
                <div className="card__body stack">
                  {SECTION_NOTES[definition.section] && (
                    <p className="profile__section-note">{SECTION_NOTES[definition.section]}</p>
                  )}

                  {recordedFields.length > 0 && (
                    <dl className="profile__entries">
                      {recordedFields.map((subField) => {
                        const values = fields!.get(subField)!
                        const [currentValue, ...history] = values
                        return (
                          <div className="profile__entry" key={subField}>
                            <dt>
                              {humanize(subField)}
                              <button
                                type="button"
                                className="btn btn--ghost btn--sm"
                                onClick={() => setAdding({ section: definition.section, subField })}
                              >
                                Update
                              </button>
                            </dt>
                            <dd>
                              <span className="profile__value">{currentValue.value}</span>
                              <span className="profile__meta">
                                {formatDate(currentValue.recorded_date)}
                                {currentValue.recorded_by ? ` · ${currentValue.recorded_by}` : ''}
                              </span>
                              {currentValue.context && (
                                <span className="profile__context">{currentValue.context}</span>
                              )}
                              {history.length > 0 && (
                                <details className="profile__history">
                                  <summary>
                                    {history.length} earlier{' '}
                                    {history.length === 1 ? 'entry' : 'entries'}
                                  </summary>
                                  <ul>
                                    {history.map((old) => (
                                      <li key={old.profile_entry_id}>
                                        <span className="profile__meta">
                                          {formatDate(old.recorded_date)}
                                        </span>
                                        {old.value}
                                        {old.context && (
                                          <span className="profile__context">{old.context}</span>
                                        )}
                                      </li>
                                    ))}
                                  </ul>
                                </details>
                              )}
                            </dd>
                          </div>
                        )
                      })}
                    </dl>
                  )}

                  <div className="profile__suggestions">
                    {suggestions.map((subField) => (
                      <button
                        key={subField}
                        type="button"
                        className="profile__chip"
                        onClick={() => setAdding({ section: definition.section, subField })}
                      >
                        + {humanize(subField)}
                      </button>
                    ))}
                    <button
                      type="button"
                      className="profile__chip profile__chip--custom"
                      onClick={() => setAdding({ section: definition.section, subField: '' })}
                    >
                      + Other…
                    </button>
                  </div>
                </div>
              </section>
            )
          })
        )}
      </div>

      {adding && (
        <AddEntryDialog
          patientId={id}
          section={adding.section}
          sectionTitle={SECTION_TITLES[adding.section]}
          initialSubField={adding.subField}
          onClose={() => setAdding(null)}
          onSaved={() => {
            setAdding(null)
            setError(null)
            entries.reload()
          }}
          onError={setError}
        />
      )}
    </div>
  )
}

function AddEntryDialog({
  patientId,
  section,
  sectionTitle,
  initialSubField,
  onClose,
  onSaved,
  onError,
}: {
  patientId: number
  section: ProfileSection
  sectionTitle: string
  initialSubField: string
  onClose: () => void
  onSaved: () => void
  onError: (message: string) => void
}) {
  const [subField, setSubField] = useState(initialSubField)
  const [value, setValue] = useState('')
  const [context, setContext] = useState('')
  const [recordedDate, setRecordedDate] = useState(today())
  const [saving, setSaving] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    try {
      await api.post<ProfileEntry>('/profile-entries', {
        patient_id: patientId,
        section,
        sub_field: subField.trim().toLowerCase().replace(/\s+/g, '_'),
        value: value.trim(),
        context: context.trim() || null,
        recorded_date: recordedDate,
      })
      onSaved()
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not save this entry.')
      onClose()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label={`Add to ${sectionTitle}`}>
      <form className="modal__panel card" onSubmit={submit}>
        <div className="card__header">
          <h2 className="card__title">
            {sectionTitle}
            {initialSubField && ` · ${humanize(initialSubField)}`}
          </h2>
        </div>
        <div className="card__body stack">
          {!initialSubField && (
            <div className="field">
              <label className="field__label" htmlFor="entry-subfield">
                Field name <span className="field__required">*</span>
              </label>
              <input
                id="entry-subfield"
                className="input"
                required
                value={subField}
                onChange={(e) => setSubField(e.target.value)}
                placeholder="e.g. caregiver status"
              />
            </div>
          )}
          <div className="field">
            <label className="field__label" htmlFor="entry-value">
              Value <span className="field__required">*</span>
            </label>
            <textarea
              id="entry-value"
              className="textarea"
              required
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="entry-context">
              Context
            </label>
            <input
              id="entry-context"
              className="input"
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="e.g. reported by patient at intake"
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="entry-date">
              Date recorded <span className="field__required">*</span>
            </label>
            <input
              id="entry-date"
              className="input"
              type="date"
              required
              value={recordedDate}
              onChange={(e) => setRecordedDate(e.target.value)}
            />
          </div>
          {initialSubField && (
            <p className="profile__section-note">
              This adds a new entry. Any existing value for this field becomes history rather than
              being overwritten.
            </p>
          )}
        </div>
        <div className="modal__actions">
          <button type="submit" className="btn btn--cta" disabled={saving}>
            {saving ? 'Saving…' : 'Add entry'}
          </button>
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
