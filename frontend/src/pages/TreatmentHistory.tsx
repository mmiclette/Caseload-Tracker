import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { useApi } from '../api/hooks'
import type { Consultation, Contact, Patient, SymptomScore } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import {
  CONTACT_LOCATION_LABELS,
  CONTACT_TYPE_LABELS,
  MEDICATION_CONFIRMATION_LABELS,
  formatDate,
  formatDateLong,
} from '../lib/format'
import { SCALES } from '../lib/scales'
import '../components/DataTable.css'
import './TreatmentHistory.css'

/**
 * Treatment History — every contact and case review for one patient,
 * expandable to its full record.
 *
 * The Clinical Dashboard lists the same events in a compact table; this
 * screen is where you open one. Scores for a contact are fetched only when
 * it's expanded, which keeps the list a single request instead of one per
 * row.
 *
 * The caseload list's clickable service dates land here with ?on=<date>,
 * so the row for that date opens automatically — that's what makes those
 * dates worth being links.
 */

type Row =
  | { kind: 'contact'; date: string; contact: Contact }
  | { kind: 'consultation'; date: string; consultation: Consultation }

export function TreatmentHistory() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)
  const [searchParams] = useSearchParams()
  const focusDate = searchParams.get('on')

  const patient = useApi<Patient>(`/patients/${id}`)
  const contacts = useApi<Contact[]>('/contacts', { patient_id: id })
  const consultations = useApi<Consultation[]>('/consultations', { patient_id: id })
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const rows = useMemo<Row[]>(() => {
    const contactRows: Row[] = (contacts.data ?? []).map((contact) => ({
      kind: 'contact',
      date: contact.contact_date,
      contact,
    }))
    const consultRows: Row[] = (consultations.data ?? []).map((consultation) => ({
      kind: 'consultation',
      date: consultation.consultation_date,
      consultation,
    }))
    return [...contactRows, ...consultRows].sort((a, b) => b.date.localeCompare(a.date))
  }, [contacts.data, consultations.data])

  // Open whatever the caseload list linked to.
  useEffect(() => {
    if (!focusDate || rows.length === 0) return
    const matches = rows
      .filter((row) => row.date === focusDate)
      .map((row) => rowKey(row))
    if (matches.length > 0) setExpanded(new Set(matches))
  }, [focusDate, rows])

  function toggle(key: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const loading = contacts.loading || consultations.loading

  return (
    <div>
      <PageHeader
        title="Treatment History"
        subtitle={
          patient.data ? (
            <>
              {patient.data.name} · MRN {patient.data.mrn}
            </>
          ) : undefined
        }
        meta={
          <div>
            <strong>{rows.length}</strong> recorded {rows.length === 1 ? 'event' : 'events'}
          </div>
        }
        actions={
          <>
            <Link className="btn btn--secondary" to={`/patients/${id}`}>
              Back to dashboard
            </Link>
            <Link className="btn btn--cta" to={`/patients/${id}/contacts/new?type=follow_up`}>
              Record contact
            </Link>
          </>
        }
      />

      {focusDate && (
        <div className="history__focus-note">
          Showing {formatDateLong(focusDate)} expanded, from the caseload list.
        </div>
      )}

      <div className="card">
        <div className="card__body--flush">
          {loading ? (
            <div className="table-loading">Loading history…</div>
          ) : rows.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__title">Nothing recorded yet</div>
              Contacts and case reviews appear here as they are recorded.
            </div>
          ) : (
            <ul className="history">
              {rows.map((row) => {
                const key = rowKey(row)
                const isOpen = expanded.has(key)
                return (
                  <li
                    key={key}
                    className={`history__item${row.date === focusDate ? ' history__item--focus' : ''}`}
                  >
                    <button
                      type="button"
                      className="history__summary"
                      onClick={() => toggle(key)}
                      aria-expanded={isOpen}
                    >
                      <span className="history__date">{formatDate(row.date)}</span>
                      <span
                        className={`history__type history__type--${
                          row.kind === 'consultation' ? 'consult' : row.contact.contact_type
                        }`}
                      >
                        {row.kind === 'consultation'
                          ? 'Psychiatric Consultation'
                          : CONTACT_TYPE_LABELS[row.contact.contact_type]}
                      </span>
                      <span className="history__meta">
                        {row.kind === 'contact'
                          ? [
                              row.contact.location
                                ? CONTACT_LOCATION_LABELS[row.contact.location]
                                : null,
                              row.contact.duration_minutes
                                ? `${row.contact.duration_minutes} min`
                                : null,
                              row.contact.attempt_number
                                ? `Attempt #${row.contact.attempt_number}`
                                : null,
                              row.contact.discuss_with_psychiatric_consultant
                                ? 'Flagged for consultant'
                                : null,
                            ]
                              .filter(Boolean)
                              .join(' · ')
                          : [
                              row.consultation.duration_minutes
                                ? `${row.consultation.duration_minutes} min`
                                : null,
                              row.consultation.recommendations_forwarded
                                ? 'Recommendations forwarded'
                                : null,
                              row.consultation.flagged_for_next_review ? 'Flagged again' : null,
                            ]
                              .filter(Boolean)
                              .join(' · ')}
                      </span>
                      <span className="history__chevron" aria-hidden="true">
                        {isOpen ? '▾' : '▸'}
                      </span>
                    </button>

                    {isOpen && (
                      <div className="history__detail">
                        {row.kind === 'contact' ? (
                          <ContactDetail contact={row.contact} />
                        ) : (
                          <ConsultationDetail consultation={row.consultation} />
                        )}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

function rowKey(row: Row): string {
  return row.kind === 'contact' ? `c-${row.contact.contact_id}` : `x-${row.consultation.consultation_id}`
}

function ContactDetail({ contact }: { contact: Contact }) {
  const [scores, setScores] = useState<SymptomScore[] | null>(null)
  const [scoresError, setScoresError] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .get<SymptomScore[]>(`/contacts/${contact.contact_id}/scores`)
      .then((result) => {
        if (!cancelled) setScores(result)
      })
      .catch(() => {
        if (!cancelled) setScoresError(true)
      })
    return () => {
      cancelled = true
    }
  }, [contact.contact_id])

  const planFields = [
    ['Other treatments', contact.other_treatments],
    ['Personal warning signs', contact.personal_warning_signs],
    ['How to minimize stress', contact.stress_reduction_plan],
    ['Additional comments', contact.additional_comments],
  ].filter(([, value]) => value) as [string, string][]

  return (
    <div className="stack">
      {scores === null && !scoresError ? (
        <p className="muted text-xs">Loading scores…</p>
      ) : scores && scores.length > 0 ? (
        <div>
          <h3 className="history__detail-title">Scores collected</h3>
          <div className="history__scores">
            {scores.map((score) => (
              <div className="history__score" key={score.score_id}>
                <span className="history__score-measure">
                  {SCALES[score.measure_type]?.title ?? score.measure_type}
                </span>
                <span className="history__score-value">{score.score_value}</span>
                {SCALES[score.measure_type]?.maxScore && (
                  <span className="history__score-max">
                    / {SCALES[score.measure_type].maxScore}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="muted text-xs">
          No scales completed at this contact. That is valid — the registry tracks the proportion of
          contacts that included one.
        </p>
      )}

      {contact.notes && (
        <div>
          <h3 className="history__detail-title">Encounter note</h3>
          <p className="history__note">{contact.notes}</p>
        </div>
      )}

      {contact.discuss_with_psychiatric_consultant && (
        <div>
          <h3 className="history__detail-title">Notes for psychiatric consultant</h3>
          <p className="history__note history__note--consultant">
            {contact.notes_for_consultant ?? 'Flagged for review with no note.'}
          </p>
        </div>
      )}

      {(planFields.length > 0 || contact.medications_confirmation) && (
        <div>
          <h3 className="history__detail-title">Relapse prevention plan</h3>
          {contact.medications_confirmation && (
            <p className="history__plan-confirm">
              Medications: {MEDICATION_CONFIRMATION_LABELS[contact.medications_confirmation]}
            </p>
          )}
          <dl className="history__plan">
            {planFields.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  )
}

function ConsultationDetail({ consultation }: { consultation: Consultation }) {
  return (
    <div className="stack">
      {consultation.notes ? (
        <div>
          <h3 className="history__detail-title">Findings and recommendations</h3>
          <p className="history__note">{consultation.notes}</p>
        </div>
      ) : (
        <p className="muted text-xs">No consultation note recorded.</p>
      )}
      {consultation.flagged_for_next_review && (
        <div>
          <h3 className="history__detail-title">Flagged for the next review</h3>
          <p className="history__note history__note--consultant">
            {consultation.flag_reason ?? 'No reason recorded.'}
          </p>
        </div>
      )}
    </div>
  )
}
