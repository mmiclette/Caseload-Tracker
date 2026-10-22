import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import { useApi } from '../api/hooks'
import type { CatalogEntry, Medication, Patient } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import '../components/DataTable.css'
import './RecordContact.css'
import './Medications.css'

/**
 * Medication management.
 *
 * The name field is a search-as-you-type picker over the vendored
 * behavioral-health catalog (GET /medications/catalog), which also supplies
 * that drug's real FDA dose strengths — so the dose control becomes a
 * dropdown of actual strengths rather than a free-text box inviting typos.
 * Combination products bring their own display doses ("8mg/2mg").
 *
 * A medication outside the catalog (metformin, a supplement) is still
 * recordable as free text; it just carries no catalog key, which is exactly
 * what keeps it out of the caseload list's psychotropic column — that
 * column means "prescribed a behavioral-health medication", and a
 * free-text entry can't be classified.
 *
 * Stopping and restarting go through PATCH, and the server owns the rules:
 * a stop reason is only valid on a past medication, and restarting clears
 * it. Identity fields never change — a different drug is a new row, which
 * keeps the history honest.
 */
export function Medications() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const patient = useApi<Patient>(`/patients/${id}`)
  const medications = useApi<Medication[]>('/medications', { patient_id: id })
  const [error, setError] = useState<string | null>(null)

  const current = (medications.data ?? []).filter((m) => m.is_current)
  const past = (medications.data ?? []).filter((m) => !m.is_current)

  async function mutate(medicationId: number, body: Record<string, unknown>) {
    setError(null)
    try {
      await api.patch(`/medications/${medicationId}`, body)
      medications.reload()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not update this medication.')
    }
  }

  return (
    <div>
      <PageHeader
        title="Medications"
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

      <div className="stack">
        <AddMedication
          patientId={id}
          onAdded={() => {
            setError(null)
            medications.reload()
          }}
          onError={setError}
        />

        <MedicationTable
          title="Current medications"
          rows={current}
          emptyNote="No current medications recorded."
          onStop={(medicationId, reason) =>
            mutate(medicationId, { is_current: false, stop_reason: reason || null })
          }
          onDoseChange={(medicationId, dose) => mutate(medicationId, { dose })}
        />

        <MedicationTable
          title="Past medications"
          rows={past}
          emptyNote="No past medications recorded."
          isPast
          onRestart={(medicationId) => mutate(medicationId, { is_current: true })}
        />
      </div>
    </div>
  )
}

function MedicationTable({
  title,
  rows,
  emptyNote,
  isPast,
  onStop,
  onRestart,
  onDoseChange,
}: {
  title: string
  rows: Medication[]
  emptyNote: string
  isPast?: boolean
  onStop?: (medicationId: number, reason: string) => void
  onRestart?: (medicationId: number) => void
  onDoseChange?: (medicationId: number, dose: string) => void
}) {
  const [stopping, setStopping] = useState<number | null>(null)
  const [reason, setReason] = useState('')

  return (
    <section className="card">
      <div className="card__header">
        <h2 className="card__title">{title}</h2>
        <span className="text-xs muted">
          {rows.length} {rows.length === 1 ? 'medication' : 'medications'}
        </span>
      </div>
      <div className="card__body--flush">
        {rows.length === 0 ? (
          <div className="empty-state">{emptyNote}</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Medication</th>
                <th>Dose</th>
                <th>Frequency</th>
                {isPast && <th>Why it was stopped</th>}
                <th>Recorded by</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((med) => (
                <tr key={med.medication_id}>
                  <td>
                    {med.medication_name}
                    {med.medication_key ? (
                      <span className="dash__badge dash__badge--quiet" title="From the behavioral-health catalog">
                        BH
                      </span>
                    ) : (
                      <span className="dash__badge dash__badge--quiet" title="Free-text entry, outside the behavioral-health catalog">
                        free text
                      </span>
                    )}
                  </td>
                  <td>
                    {onDoseChange ? (
                      <EditableDose
                        med={med}
                        onSave={(dose) => onDoseChange(med.medication_id, dose)}
                      />
                    ) : (
                      (med.dose ?? '—')
                    )}
                  </td>
                  <td>{med.frequency ?? '—'}</td>
                  {isPast && (
                    <td className="muted">
                      {med.stop_reason ?? <span title="Unknown history is real data">Not recorded</span>}
                    </td>
                  )}
                  <td className="muted text-xs">{med.recorded_by ?? '—'}</td>
                  <td className="is-center">
                    {onRestart && (
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        onClick={() => onRestart(med.medication_id)}
                      >
                        Restart
                      </button>
                    )}
                    {onStop && stopping !== med.medication_id && (
                      <button
                        type="button"
                        className="btn btn--secondary btn--sm"
                        onClick={() => {
                          setStopping(med.medication_id)
                          setReason('')
                        }}
                      >
                        Stop
                      </button>
                    )}
                    {onStop && stopping === med.medication_id && (
                      <span className="med__stop-row">
                        <input
                          className="input med__stop-reason"
                          placeholder="Why was it stopped? (optional)"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                        />
                        <button
                          type="button"
                          className="btn btn--cta btn--sm"
                          onClick={() => {
                            onStop(med.medication_id, reason)
                            setStopping(null)
                          }}
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          className="btn btn--ghost btn--sm"
                          onClick={() => setStopping(null)}
                        >
                          Cancel
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

function EditableDose({ med, onSave }: { med: Medication; onSave: (dose: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(med.dose ?? '')
  if (!editing) {
    return (
      <button type="button" className="med__inline-edit" onClick={() => setEditing(true)}>
        {med.dose ?? <span className="muted">Set dose</span>}
      </button>
    )
  }
  return (
    <span className="med__stop-row">
      <input
        className="input med__dose-input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoFocus
      />
      <button
        type="button"
        className="btn btn--cta btn--sm"
        onClick={() => {
          onSave(value)
          setEditing(false)
        }}
      >
        Save
      </button>
      <button type="button" className="btn btn--ghost btn--sm" onClick={() => setEditing(false)}>
        Cancel
      </button>
    </span>
  )
}

function AddMedication({
  patientId,
  onAdded,
  onError,
}: {
  patientId: number
  onAdded: () => void
  onError: (message: string) => void
}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<CatalogEntry[]>([])
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<CatalogEntry | null>(null)
  const [freeText, setFreeText] = useState('')
  const [dose, setDose] = useState('')
  const [frequency, setFrequency] = useState('')
  const [saving, setSaving] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const term = query.trim()
    if (term.length < 2 || selected) {
      setResults([])
      return
    }
    let cancelled = false
    const timer = setTimeout(() => {
      api
        .get<CatalogEntry[]>('/medications/catalog', { q: term, limit: 8 })
        .then((entries) => {
          if (cancelled) return
          setResults(entries)
          setOpen(true)
        })
        .catch(() => {
          if (!cancelled) setResults([])
        })
    }, 180)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query, selected])

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  function pick(entry: CatalogEntry) {
    setSelected(entry)
    setQuery(entry.display)
    setOpen(false)
    setDose(entry.doses[0] ?? '')
  }

  function reset() {
    setSelected(null)
    setQuery('')
    setFreeText('')
    setDose('')
    setFrequency('')
    setResults([])
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setSaving(true)
    try {
      await api.post<Medication>('/medications', {
        patient_id: patientId,
        medication_key: selected?.key ?? null,
        medication_name: selected ? null : freeText.trim() || query.trim(),
        dose: dose || null,
        frequency: frequency.trim() || null,
        is_current: true,
      })
      reset()
      onAdded()
    } catch (err) {
      onError(err instanceof ApiError ? err.message : 'Could not add this medication.')
    } finally {
      setSaving(false)
    }
  }

  const usingFreeText = !selected && (freeText.trim().length > 0 || results.length === 0)

  return (
    <form className="card" onSubmit={submit}>
      <div className="card__header">
        <h2 className="card__title">Add a medication</h2>
        <span className="text-xs muted">Search the behavioral-health catalog, or type any name</span>
      </div>
      <div className="card__body med__add-grid">
        <div className="field med__search-field" ref={containerRef}>
          <label className="field__label" htmlFor="med-search">
            Medication <span className="field__required">*</span>
          </label>
          <input
            id="med-search"
            className="input"
            required
            value={query}
            placeholder="Start typing — e.g. sertraline, Zoloft, metformin"
            onChange={(e) => {
              setQuery(e.target.value)
              setSelected(null)
              setDose('')
            }}
            onFocus={() => results.length > 0 && setOpen(true)}
            autoComplete="off"
          />
          {open && results.length > 0 && (
            <ul className="med__results">
              {results.map((entry) => (
                <li key={entry.key}>
                  <button type="button" onClick={() => pick(entry)}>
                    <span className="med__result-name">{entry.display}</span>
                    <span className="med__result-meta">
                      {entry.med_class} · {entry.doses.length} dose
                      {entry.doses.length === 1 ? '' : 's'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {selected ? (
            <span className="med__hint med__hint--matched">
              Matched {selected.med_class} in the catalog — counts toward the psychotropic column
            </span>
          ) : (
            usingFreeText &&
            query.trim().length >= 2 && (
              <span className="med__hint">
                No catalog match — this will be saved as free text and will not count toward the
                psychotropic column
              </span>
            )
          )}
        </div>

        <div className="field">
          <label className="field__label" htmlFor="med-dose">
            Dose
          </label>
          {selected && selected.doses.length > 0 ? (
            <select
              id="med-dose"
              className="select"
              value={dose}
              onChange={(e) => setDose(e.target.value)}
            >
              <option value="">—</option>
              {selected.doses.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="med-dose"
              className="input"
              value={dose}
              onChange={(e) => setDose(e.target.value)}
              placeholder="e.g. 500 mg"
            />
          )}
        </div>

        <div className="field">
          <label className="field__label" htmlFor="med-frequency">
            Frequency
          </label>
          <input
            id="med-frequency"
            className="input"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
            placeholder="e.g. daily, twice daily"
          />
        </div>

        <div className="med__add-actions">
          <button type="submit" className="btn btn--cta" disabled={saving || query.trim().length < 2}>
            {saving ? 'Adding…' : 'Add medication'}
          </button>
        </div>
      </div>
    </form>
  )
}
