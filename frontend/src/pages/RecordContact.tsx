import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { useApi } from '../api/hooks'
import type {
  Contact,
  ContactLocation,
  ContactType,
  Episode,
  MeasureType,
  MedicationConfirmation,
  Patient,
  Provider,
  SymptomScore,
} from '../api/types'
import { PageHeader } from '../components/PageHeader'
import {
  EMPTY_RESPONSE,
  ScaleEntry,
  resolveScore,
  type ScaleResponse,
} from '../components/ScaleEntry'
import {
  CONTACT_LOCATION_LABELS,
  CONTACT_TYPE_LABELS,
  DURATION_OPTIONS,
  MEDICATION_CONFIRMATION_LABELS,
  formatDate,
} from '../lib/format'
import { CONDITION_DEFAULT_MEASURES, SCALES, SELECTABLE_MEASURES } from '../lib/scales'
import './RecordContact.css'

/**
 * The contact-recording form — the CTMS's central write screen.
 *
 * One save action covers the visit date, every scale collected that day,
 * the discuss-with-consultant checkbox, the encounter note, and the session
 * footer, because that's exactly what POST /contacts accepts in one call
 * (ContactService.record_contact). Splitting it would break the server-side
 * cascades that call depends on — baseline recompute, the RPP status
 * transition, the yellow-flag set, attempt numbering.
 *
 * Scale selection carries forward: the measures on the patient's most
 * recent scored contact are pre-checked, matching the CTMS ("whichever
 * scales are selected for a patient carry forward to their next contact by
 * default"), falling back to the episode's diagnoses for a first visit.
 */

const CONTACT_TYPE_OPTIONS: ContactType[] = [
  'initial_assessment',
  'follow_up',
  'relapse_prevention_plan',
  'contact_attempt',
  'care_team_collaboration',
]

const LOCATION_OPTIONS: ContactLocation[] = ['phone', 'in_clinic', 'virtual']

/** Contact types that never carry scores (enforced by ContactService too). */
const NON_SCORING: ContactType[] = ['contact_attempt', 'care_team_collaboration']

function today(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export function RecordContact() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const patient = useApi<Patient>(`/patients/${id}`)
  const episodes = useApi<Episode[]>('/episodes', { patient_id: id })
  const providers = useApi<Provider[]>('/providers', { limit: 200 })
  const priorContacts = useApi<Contact[]>('/contacts', { patient_id: id })

  const requestedType = searchParams.get('type') as ContactType | null
  const [contactType, setContactType] = useState<ContactType>(
    requestedType && CONTACT_TYPE_OPTIONS.includes(requestedType) ? requestedType : 'follow_up',
  )
  const [contactDate, setContactDate] = useState(searchParams.get('on') ?? today())
  const [location, setLocation] = useState<ContactLocation | ''>('')
  const [providerId, setProviderId] = useState<string>('')
  const [durationMinutes, setDurationMinutes] = useState<string>('')
  const [notes, setNotes] = useState('')
  const [discuss, setDiscuss] = useState(false)
  const [consultantNotes, setConsultantNotes] = useState('')

  // Relapse Prevention Plan content (only sent on an RPP contact).
  const [otherTreatments, setOtherTreatments] = useState('')
  const [warningSigns, setWarningSigns] = useState('')
  const [stressPlan, setStressPlan] = useState('')
  const [additionalComments, setAdditionalComments] = useState('')
  const [medsConfirmation, setMedsConfirmation] = useState<MedicationConfirmation | ''>('')

  const [selectedMeasures, setSelectedMeasures] = useState<MeasureType[]>([])
  const [responses, setResponses] = useState<Record<string, ScaleResponse>>({})
  const [initialised, setInitialised] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const openEpisode = useMemo(
    () => (episodes.data ?? []).find((e) => e.end_date === null) ?? null,
    [episodes.data],
  )

  // Carry-forward: pre-check the scales used on the last scored contact.
  useEffect(() => {
    if (initialised || !priorContacts.data || !episodes.data) return
    const scored = [...priorContacts.data]
      .filter((c) => !NON_SCORING.includes(c.contact_type))
      .sort((a, b) => b.contact_date.localeCompare(a.contact_date))

    async function seed() {
      let measures: MeasureType[] = []
      for (const contact of scored) {
        try {
          const scores = await api.get<SymptomScore[]>(`/contacts/${contact.contact_id}/scores`)
          if (scores.length > 0) {
            measures = [...new Set(scores.map((s) => s.measure_type))]
            break
          }
        } catch {
          /* a missing score list shouldn't block the form */
        }
      }
      if (measures.length === 0 && openEpisode) {
        const conditions = [openEpisode.primary_diagnosis, openEpisode.secondary_diagnosis].filter(
          Boolean,
        ) as string[]
        measures = conditions.flatMap((c) => CONDITION_DEFAULT_MEASURES[c] ?? [])
      }
      const unique = [...new Set(measures)]
      setSelectedMeasures(unique)
      setResponses(Object.fromEntries(unique.map((m) => [m, { ...EMPTY_RESPONSE }])))
      setInitialised(true)
    }
    void seed()
  }, [initialised, priorContacts.data, episodes.data, openEpisode])

  const scoresAllowed = !NON_SCORING.includes(contactType)
  const isRpp = contactType === 'relapse_prevention_plan'

  function toggleMeasure(measure: MeasureType) {
    setSelectedMeasures((current) => {
      if (current.includes(measure)) {
        return current.filter((m) => m !== measure)
      }
      setResponses((r) => ({ ...r, [measure]: r[measure] ?? { ...EMPTY_RESPONSE } }))
      return [...current, measure]
    })
  }

  const preparedScores = useMemo(
    () =>
      selectedMeasures
        .map((measure) => ({
          measure_type: measure,
          score_value: resolveScore(measure, responses[measure] ?? EMPTY_RESPONSE),
        }))
        .filter((s): s is { measure_type: MeasureType; score_value: number } => s.score_value !== null),
    [selectedMeasures, responses],
  )

  const incompleteScales = selectedMeasures.filter(
    (m) => resolveScore(m, responses[m] ?? EMPTY_RESPONSE) === null,
  )

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)

    if (scoresAllowed && preparedScores.length > 0 && !openEpisode) {
      setError('Recording scores requires an open episode of care for this patient.')
      return
    }

    setSaving(true)
    try {
      await api.post<Contact>('/contacts', {
        patient_id: id,
        episode_id: openEpisode?.episode_id ?? null,
        provider_id: providerId ? Number(providerId) : null,
        contact_type: contactType,
        contact_date: contactDate,
        location: location || null,
        duration_minutes: durationMinutes ? Number(durationMinutes) : null,
        discuss_with_psychiatric_consultant: scoresAllowed ? discuss : false,
        notes_for_consultant: discuss && consultantNotes ? consultantNotes : null,
        notes: notes || null,
        ...(isRpp
          ? {
              other_treatments: otherTreatments || null,
              personal_warning_signs: warningSigns || null,
              stress_reduction_plan: stressPlan || null,
              additional_comments: additionalComments || null,
              medications_confirmation: medsConfirmation || null,
            }
          : {}),
        scores: scoresAllowed ? preparedScores : [],
      })
      navigate(`/patients/${id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save this contact.')
    } finally {
      setSaving(false)
    }
  }

  if (patient.loading) {
    return (
      <div>
        <PageHeader title="Record a contact" />
        <div className="card">
          <div className="table-loading">Loading patient…</div>
        </div>
      </div>
    )
  }

  if (patient.error || !patient.data) {
    return (
      <div>
        <PageHeader title="Record a contact" />
        <div className="error-banner" role="alert">
          {patient.error ?? 'Patient not found.'}
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={onSubmit}>
      <PageHeader
        title={CONTACT_TYPE_LABELS[contactType]}
        subtitle={
          <>
            {patient.data.name} · MRN {patient.data.mrn}
          </>
        }
        meta={
          openEpisode ? (
            <>
              <div>Episode opened {formatDate(openEpisode.start_date)}</div>
              {openEpisode.primary_diagnosis && (
                <div>Primary: {openEpisode.primary_diagnosis.replace(/_/g, ' ')}</div>
              )}
            </>
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

      <div className="stack">
        <section className="card">
          <div className="card__header">
            <h2 className="card__title">Contact</h2>
          </div>
          <div className="card__body contact-form__grid">
            <div className="field">
              <label className="field__label" htmlFor="contact-type">
                Type <span className="field__required">*</span>
              </label>
              <select
                id="contact-type"
                className="select"
                value={contactType}
                onChange={(e) => setContactType(e.target.value as ContactType)}
              >
                {CONTACT_TYPE_OPTIONS.map((type) => (
                  <option key={type} value={type}>
                    {CONTACT_TYPE_LABELS[type]}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="field__label" htmlFor="contact-date">
                Date of contact <span className="field__required">*</span>
              </label>
              <div className="row">
                <input
                  id="contact-date"
                  className="input"
                  type="date"
                  required
                  value={contactDate}
                  onChange={(e) => setContactDate(e.target.value)}
                />
                <button
                  type="button"
                  className="btn btn--secondary btn--sm"
                  onClick={() => setContactDate(today())}
                >
                  Today
                </button>
              </div>
            </div>
          </div>

          {!scoresAllowed && (
            <div className="contact-form__notice">
              {contactType === 'contact_attempt'
                ? 'A contact attempt records outreach that did not reach the patient. It carries no scale scores and does not reset the follow-up reminder.'
                : 'Care team collaboration is work about the patient without the patient present. Its minutes count toward billing, but it carries no scale scores and is not counted as a session or as engagement.'}
            </div>
          )}
        </section>

        {scoresAllowed && (
          <section className="card">
            <div className="card__header">
              <h2 className="card__title">Outcome measures</h2>
              <span className="text-xs muted">
                {initialised && selectedMeasures.length > 0
                  ? 'Carried forward from the last contact'
                  : 'Select the scales completed today'}
              </span>
            </div>
            <div className="card__body stack">
              <div className="contact-form__measure-picker">
                {SELECTABLE_MEASURES.map((measure) => (
                  <label key={measure} className="contact-form__measure">
                    <input
                      type="checkbox"
                      checked={selectedMeasures.includes(measure)}
                      onChange={() => toggleMeasure(measure)}
                    />
                    {SCALES[measure].title}
                  </label>
                ))}
              </div>

              {selectedMeasures.length === 0 ? (
                <p className="muted text-xs">
                  No scales selected. A completed visit without a scale is valid — the registry
                  tracks the proportion of contacts that included one.
                </p>
              ) : (
                selectedMeasures.map((measure) => (
                  <ScaleEntry
                    key={measure}
                    measureType={measure}
                    response={responses[measure] ?? EMPTY_RESPONSE}
                    onChange={(next) => setResponses((r) => ({ ...r, [measure]: next }))}
                    onRemove={() => toggleMeasure(measure)}
                  />
                ))
              )}

              {incompleteScales.length > 0 && (
                <p className="contact-form__hint">
                  {incompleteScales.map((m) => SCALES[m].title).join(', ')} will not be saved until
                  every item is answered or a total is entered.
                </p>
              )}
            </div>
          </section>
        )}

        {isRpp && (
          <section className="card">
            <div className="card__header">
              <h2 className="card__title">Relapse prevention plan</h2>
            </div>
            <div className="card__body stack">
              <div className="field">
                <span className="field__label">Current medications</span>
                <div className="contact-form__radio-row">
                  {(Object.keys(MEDICATION_CONFIRMATION_LABELS) as MedicationConfirmation[]).map(
                    (value) => (
                      <label key={value} className="contact-form__radio">
                        <input
                          type="radio"
                          name="meds-confirmation"
                          checked={medsConfirmation === value}
                          onChange={() => setMedsConfirmation(value)}
                        />
                        {MEDICATION_CONFIRMATION_LABELS[value]}
                      </label>
                    ),
                  )}
                </div>
              </div>
              <PlanField
                id="other-treatments"
                label="Other treatments"
                placeholder="e.g. Counseling"
                value={otherTreatments}
                onChange={setOtherTreatments}
              />
              <PlanField
                id="warning-signs"
                label="Personal warning signs"
                placeholder="e.g. Signs of worsening depression or anxiety"
                value={warningSigns}
                onChange={setWarningSigns}
              />
              <PlanField
                id="stress-plan"
                label="How to minimize stress from depression or anxiety"
                placeholder="e.g. physical or social activities"
                value={stressPlan}
                onChange={setStressPlan}
              />
              <PlanField
                id="additional-comments"
                label="Additional comments"
                value={additionalComments}
                onChange={setAdditionalComments}
              />
            </div>
          </section>
        )}

        {scoresAllowed && (
          <section className="card">
            <div className="card__header">
              <h2 className="card__title">Discuss with psychiatric consultant</h2>
            </div>
            <div className="card__body stack">
              <label className="contact-form__checkbox">
                <input
                  type="checkbox"
                  checked={discuss}
                  onChange={(e) => setDiscuss(e.target.checked)}
                />
                Would you like to discuss this patient with the psychiatric consultant?
              </label>
              {discuss && (
                <>
                  <div className="field">
                    <label className="field__label" htmlFor="consultant-notes">
                      Notes for psychiatric consultant
                    </label>
                    <textarea
                      id="consultant-notes"
                      className="textarea"
                      value={consultantNotes}
                      onChange={(e) => setConsultantNotes(e.target.value)}
                    />
                  </div>
                  <p className="contact-form__hint">
                    Saving this flags the patient for the next Systematic Caseload Review. The flag
                    clears automatically once a consultation is recorded.
                  </p>
                </>
              )}
            </div>
          </section>
        )}

        <section className="card">
          <div className="card__header">
            <h2 className="card__title">Encounter note</h2>
          </div>
          <div className="card__body">
            <div className="field">
              <label className="field__label" htmlFor="encounter-note">
                What happened during this contact
              </label>
              <textarea
                id="encounter-note"
                className="textarea contact-form__note"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>
        </section>

        {/* The CTMS's one-sentence session footer. */}
        <section className="card">
          <div className="card__body contact-form__footer">
            <span>This session was</span>
            <select
              className="select contact-form__inline-select"
              aria-label="Session location"
              value={location}
              onChange={(e) => setLocation(e.target.value as ContactLocation | '')}
            >
              <option value="">—</option>
              {LOCATION_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {CONTACT_LOCATION_LABELS[value]}
                </option>
              ))}
            </select>
            <span>with</span>
            <select
              className="select contact-form__inline-select"
              aria-label="Provider"
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
            >
              <option value="">—</option>
              {(providers.data ?? []).map((p) => (
                <option key={p.provider_id} value={p.provider_id}>
                  {p.name}
                </option>
              ))}
            </select>
            <span>and took</span>
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
            {saving ? 'Saving…' : 'Save contact'}
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => navigate(`/patients/${id}`)}
          >
            Cancel
          </button>
          {preparedScores.length > 0 && (
            <span className="text-xs muted">
              Saving {preparedScores.length} {preparedScores.length === 1 ? 'score' : 'scores'}:{' '}
              {preparedScores.map((s) => `${SCALES[s.measure_type].title} ${s.score_value}`).join(', ')}
            </span>
          )}
        </div>
      </div>
    </form>
  )
}

function PlanField({
  id,
  label,
  placeholder,
  value,
  onChange,
}: {
  id: string
  label: string
  placeholder?: string
  value: string
  onChange: (next: string) => void
}) {
  return (
    <div className="field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <textarea
        id={id}
        className="textarea"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}
