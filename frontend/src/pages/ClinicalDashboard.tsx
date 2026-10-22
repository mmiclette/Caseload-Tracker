import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApi } from '../api/hooks'
import type {
  ClinicalDashboard as Dashboard,
  Consultation,
  Contact,
  Reminder,
} from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { ScoreChart } from '../components/ScoreChart'
import { Flags, StatusPill } from '../components/cells'
import {
  CONDITION_LABELS,
  CONTACT_LOCATION_LABELS,
  CONTACT_TYPE_LABELS,
  END_REASON_LABELS,
  MEDICATION_CONFIRMATION_LABELS,
  PROVIDER_ROLE_LABELS,
  formatDate,
  formatDateLong,
  humanize,
} from '../lib/format'
import '../components/DataTable.css'
import './ClinicalDashboard.css'

/**
 * The Clinical Dashboard — the single-patient view.
 *
 * Composed from four endpoints rather than one: the dashboard report gives
 * demographics, providers, clinics, episodes, scores, medications, profile
 * entries and measure trends, but not contacts, consultations, or reminders
 * (that composition gap is documented in docs/ctms-reference/README.md).
 * Fetching them alongside is what lets this page show Treatment History and
 * Next Appointment without a backend change.
 *
 * "Customize Dashboard View" is a frontend concern by design — the endpoint
 * always returns everything and this component decides what to render,
 * exactly as CLAUDE.md describes.
 */

const SECTION_KEYS = [
  'trends',
  'patient',
  'medications',
  'profile',
  'consultant',
  'history',
  'episodes',
] as const
type SectionKey = (typeof SECTION_KEYS)[number]

const SECTION_LABELS: Record<SectionKey, string> = {
  trends: 'Clinical Measures',
  patient: 'Patient Information',
  medications: 'Medications',
  profile: 'Patient Profile',
  consultant: 'Psychiatric Consultant',
  history: 'Treatment History',
  episodes: 'Episode History',
}

const NON_ENCOUNTER: Contact['contact_type'][] = ['contact_attempt', 'care_team_collaboration']

export function ClinicalDashboard() {
  const { patientId } = useParams<{ patientId: string }>()
  const id = Number(patientId)

  const dashboard = useApi<Dashboard>(`/reports/clinical-dashboard/${id}`)
  const contacts = useApi<Contact[]>('/contacts', { patient_id: id })
  const consultations = useApi<Consultation[]>('/consultations', { patient_id: id })
  const reminders = useApi<Reminder[]>('/reminders', { patient_id: id })

  const [visible, setVisible] = useState<Record<SectionKey, boolean>>(
    () => Object.fromEntries(SECTION_KEYS.map((k) => [k, true])) as Record<SectionKey, boolean>,
  )

  const data = dashboard.data
  const contactList = contacts.data ?? []

  const firstContactDate = useMemo(() => {
    const encounters = contactList
      .filter((c) => !NON_ENCOUNTER.includes(c.contact_type))
      .map((c) => c.contact_date)
      .sort()
    return encounters[0] ?? null
  }, [contactList])

  const lastContact = useMemo(() => {
    const encounters = contactList
      .filter((c) => !NON_ENCOUNTER.includes(c.contact_type))
      .sort((a, b) => b.contact_date.localeCompare(a.contact_date))
    return encounters[0] ?? null
  }, [contactList])

  const nextAppointment = useMemo(
    () =>
      (reminders.data ?? [])
        .filter((r) => r.status === 'pending' && r.reminder_type === 'appointment')
        .sort((a, b) => a.due_date.localeCompare(b.due_date))[0] ?? null,
    [reminders.data],
  )

  if (dashboard.loading) {
    return (
      <div>
        <PageHeader title="Clinical Dashboard" />
        <div className="card">
          <div className="table-loading">Loading patient…</div>
        </div>
      </div>
    )
  }

  if (dashboard.error || !data) {
    return (
      <div>
        <PageHeader title="Clinical Dashboard" />
        <div className="error-banner" role="alert">
          {dashboard.error ?? 'Patient not found.'}
        </div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title={data.name}
        subtitle={
          <span className="dash__subtitle">
            {data.current_status && <StatusPill status={data.current_status} />}
            <span>
              Patient ID {String(data.patient_id).padStart(8, '0')} · MRN {data.mrn}
            </span>
          </span>
        }
        meta={
          <>
            <div>
              Age {data.age} · DOB {formatDate(data.date_of_birth)}
            </div>
            <div>{data.payer}</div>
          </>
        }
        actions={
          <>
            <Link className="btn btn--cta" to={`/patients/${id}/contacts/new?type=follow_up`}>
              Record contact
            </Link>
            <Link
              className="btn btn--secondary"
              to={`/patients/${id}/contacts/new?type=initial_assessment`}
            >
              Initial assessment
            </Link>
            <Link className="btn btn--secondary" to={`/patients/${id}/consultations/new`}>
              Psychiatric consultation
            </Link>
            <Link className="btn btn--secondary" to={`/patients/${id}/contacts`}>
              Treatment history
            </Link>
            {data.current_status !== 'deactivated' && (
              <Link className="btn btn--ghost" to={`/patients/${id}/deactivate`}>
                Deactivate
              </Link>
            )}
          </>
        }
      />

      <div className="dash">
        {/* ---- Left rail ---- */}
        <aside className="dash__rail">
          <div className="card dash__rail-card">
            <div className="dash__rail-title">Customize dashboard view</div>
            <div className="dash__toggles">
              {SECTION_KEYS.map((key) => (
                <label key={key} className="dash__toggle">
                  <input
                    type="checkbox"
                    checked={visible[key]}
                    onChange={(e) => setVisible((v) => ({ ...v, [key]: e.target.checked }))}
                  />
                  <span className={`dash__toggle-pill${visible[key] ? ' is-on' : ''}`}>
                    {visible[key] ? 'ON' : 'OFF'}
                  </span>
                  {SECTION_LABELS[key]}
                </label>
              ))}
            </div>
          </div>

          <div className="card dash__rail-card">
            <div className="dash__rail-title">Flags</div>
            <div className="dash__rail-body">
              <div className="dash__flag-row">
                <Flags
                  needsReview={data.needs_psychiatric_review}
                  safetyRisk={data.safety_risk}
                  customActive={data.custom_flag_active}
                  customLabel={data.custom_flag_label}
                />
                <span className="text-xs muted">
                  {data.needs_psychiatric_review ? 'Flagged for review' : 'No review flag'}
                </span>
              </div>
              {data.safety_risk && <div className="dash__alert">Safety risk on file</div>}
              {data.custom_flag_active && (
                <div className="text-xs">{data.custom_flag_label ?? 'Custom flag'}</div>
              )}
            </div>
          </div>

          <div className="card dash__rail-card">
            <div className="dash__rail-title">Last contact</div>
            <div className="dash__rail-body">
              {lastContact ? (
                <>
                  <div className="dash__rail-strong">{formatDateLong(lastContact.contact_date)}</div>
                  <div className="text-xs muted">
                    {CONTACT_TYPE_LABELS[lastContact.contact_type]}
                    {lastContact.location
                      ? ` · ${CONTACT_LOCATION_LABELS[lastContact.location]}`
                      : ''}
                  </div>
                </>
              ) : (
                <span className="muted text-xs">No completed contacts yet</span>
              )}
            </div>
          </div>

          <div className="card dash__rail-card">
            <div className="dash__rail-title">Next appointment</div>
            <div className="dash__rail-body">
              {nextAppointment ? (
                <div
                  className={`dash__rail-strong${
                    nextAppointment.due_date < new Date().toISOString().slice(0, 10)
                      ? ' dash__rail-strong--overdue'
                      : ''
                  }`}
                >
                  {formatDateLong(nextAppointment.due_date)}
                </div>
              ) : (
                <span className="muted text-xs">None scheduled</span>
              )}
            </div>
          </div>

          <div className="card dash__rail-card">
            <div className="dash__rail-title">Status</div>
            <div className="dash__rail-body">
              {data.current_status ? (
                <>
                  <StatusPill status={data.current_status} />
                  <div className="text-xs muted">
                    since {formatDate(data.status_changed_date)}
                  </div>
                </>
              ) : (
                <span className="muted text-xs">No status recorded</span>
              )}
            </div>
          </div>
        </aside>

        {/* ---- Main column ---- */}
        <div className="dash__main stack">
          {visible.trends && (
            <section className="card">
              <div className="card__header">
                <h2 className="card__title">Clinical Measures</h2>
                <span className="text-xs muted">
                  {data.measure_trends.length > 0
                    ? 'One graph per treated diagnosis'
                    : 'No diagnosis recorded'}
                </span>
              </div>
              <div className="card__body">
                {data.measure_trends.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-state__title">No measure trends yet</div>
                    Trends appear once the episode has a primary diagnosis and at least one score.
                  </div>
                ) : (
                  <div className="dash__trends">
                    {data.measure_trends.map((trend) => (
                      <div className="dash__trend" key={`${trend.condition}-${trend.measure_type}`}>
                        <div className="dash__trend-head">
                          <div>
                            <span className="dash__trend-title">
                              {CONDITION_LABELS[trend.condition]}
                            </span>
                            <span className="dash__trend-measure">{trend.measure_type}</span>
                            {trend.is_primary && <span className="dash__badge">Primary</span>}
                          </div>
                          <div className="dash__trend-outcomes">
                            {trend.is_remission && (
                              <span className="dash__outcome dash__outcome--good">Remission</span>
                            )}
                            {trend.is_response && (
                              <span className="dash__outcome dash__outcome--good">Response</span>
                            )}
                            {trend.is_response === false && !trend.is_remission && (
                              <span className="dash__outcome dash__outcome--watch">
                                Not yet responding
                              </span>
                            )}
                            {trend.is_response === null && (
                              <span
                                className="dash__outcome"
                                title="Response needs at least two scores of the same measure"
                              >
                                Awaiting follow-up score
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="dash__trend-figures">
                          <Figure label="Baseline" value={trend.baseline_score} date={trend.baseline_date} />
                          <Figure label="Most recent" value={trend.latest_score} date={trend.latest_date} />
                          <Figure
                            label="Change"
                            value={
                              trend.baseline_score !== null && trend.latest_score !== null
                                ? trend.latest_score - trend.baseline_score
                                : null
                            }
                            signed
                          />
                        </div>
                        <ScoreChart trend={trend} firstContactDate={firstContactDate} />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          )}

          {visible.patient && (
            <section className="card">
              <div className="card__header">
                <h2 className="card__title">Patient Information</h2>
              </div>
              <div className="card__body stack">
                <SubSection title="Enrollment">
                  <dl className="dash__facts">
                    <Fact label="Enrollment date" value={formatDateLong(data.enrollment_date)} />
                    <Fact label="Consent date" value={formatDateLong(data.consent_date)} />
                    <Fact label="Payer" value={data.payer} />
                    <Fact
                      label="Deactivated"
                      value={data.deactivation_date ? formatDateLong(data.deactivation_date) : '—'}
                    />
                  </dl>
                </SubSection>

                <SubSection title="Demographics">
                  <dl className="dash__facts">
                    <Fact label="Date of birth" value={formatDateLong(data.date_of_birth)} />
                    <Fact label="Age" value={String(data.age)} />
                    <Fact
                      label="Race / ethnicity"
                      value={data.race_ethnicity?.join(', ') || '—'}
                    />
                    <Fact
                      label="Program eligibility"
                      value={
                        data.program_eligibility
                          ? Object.entries(data.program_eligibility)
                              .map(([k, v]) => `${humanize(k)}: ${String(v)}`)
                              .join(' · ')
                          : '—'
                      }
                    />
                  </dl>
                </SubSection>

                <SubSection title="Current providers">
                  {data.current_providers.length === 0 ? (
                    <p className="muted text-xs">No current care team assignments.</p>
                  ) : (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Type</th>
                          <th>Name</th>
                          <th>Phone</th>
                          <th>Email</th>
                          <th>Service begin</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.current_providers.map((p) => (
                          <tr key={`${p.provider_id}-${p.role}`}>
                            <td>{PROVIDER_ROLE_LABELS[p.role]}</td>
                            <td>{p.name}</td>
                            <td className="muted">{p.phone ?? '—'}</td>
                            <td className="muted">{p.email ?? '—'}</td>
                            <td className="nowrap">{formatDate(p.service_begin_date)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </SubSection>

                <SubSection title="Current clinics">
                  {data.current_clinics.length === 0 ? (
                    <p className="muted text-xs">No current clinic assignments.</p>
                  ) : (
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Clinic</th>
                          <th className="is-center">Primary</th>
                          <th>Service begin</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.current_clinics.map((c) => (
                          <tr key={c.clinic_id}>
                            <td>{c.clinic_id}</td>
                            <td className="is-center">
                              {c.is_primary ? <span className="check-mark">✓</span> : ''}
                            </td>
                            <td className="nowrap">{formatDate(c.service_begin_date)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </SubSection>
              </div>
            </section>
          )}

          {visible.medications && (
            <section className="card">
              <div className="card__header">
                <h2 className="card__title">Medications</h2>
                <Link className="btn btn--ghost btn--sm" to={`/patients/${id}/medications`}>
                  Manage
                </Link>
              </div>
              <div className="card__body--flush">
                {data.medications.length === 0 ? (
                  <div className="empty-state">No medications recorded.</div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Medication</th>
                        <th>Dose</th>
                        <th>Frequency</th>
                        <th className="is-center">Current</th>
                        <th>Stop reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.medications.map((m) => (
                        <tr key={m.medication_id}>
                          <td>
                            {m.medication_name}
                            {m.medication_key && (
                              <span className="dash__badge dash__badge--quiet">BH</span>
                            )}
                          </td>
                          <td>{m.dose ?? '—'}</td>
                          <td>{m.frequency ?? '—'}</td>
                          <td className="is-center">
                            {m.is_current ? (
                              <span className="check-mark">✓</span>
                            ) : (
                              <span className="muted">—</span>
                            )}
                          </td>
                          <td className="muted">{m.stop_reason ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          )}

          {visible.profile && <ProfileSections entries={data.profile_entries} patientId={id} />}

          {visible.consultant && (
            <section className="card">
              <div className="card__header">
                <h2 className="card__title">Psychiatric Consultant</h2>
                <Link className="btn btn--ghost btn--sm" to={`/patients/${id}/consultations/new`}>
                  Record consultation
                </Link>
              </div>
              <div className="card__body--flush">
                {(consultations.data ?? []).length === 0 ? (
                  <div className="empty-state">No consultations recorded.</div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th className="is-numeric">Minutes</th>
                        <th className="is-center">Recs forwarded</th>
                        <th className="is-center">Flagged for next review</th>
                        <th>Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...(consultations.data ?? [])]
                        .sort((a, b) => b.consultation_date.localeCompare(a.consultation_date))
                        .map((c) => (
                          <tr key={c.consultation_id}>
                            <td className="nowrap">{formatDate(c.consultation_date)}</td>
                            <td className="is-numeric">{c.duration_minutes ?? '—'}</td>
                            <td className="is-center">
                              {c.recommendations_forwarded ? (
                                <span className="check-mark">✓</span>
                              ) : (
                                <span className="muted">—</span>
                              )}
                            </td>
                            <td className="is-center">
                              {c.flagged_for_next_review ? (
                                <span className="consider-badge">FLAGGED</span>
                              ) : (
                                <span className="muted">—</span>
                              )}
                            </td>
                            <td className="dash__note-cell">{c.notes ?? '—'}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          )}

          {visible.history && (
            <TreatmentHistory
              patientId={id}
              contacts={contactList}
              consultations={consultations.data ?? []}
              firstContactDate={firstContactDate}
              loading={contacts.loading}
            />
          )}

          {visible.episodes && (
            <section className="card">
              <div className="card__header">
                <h2 className="card__title">Episode History</h2>
              </div>
              <div className="card__body--flush">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Start</th>
                      <th>End</th>
                      <th>End reason</th>
                      <th>Baseline measure</th>
                      <th className="is-numeric">Baseline score</th>
                      <th>Baseline date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.episodes.map((e) => (
                      <tr key={e.episode_id}>
                        <td className="nowrap">{formatDate(e.start_date)}</td>
                        <td className="nowrap">{e.end_date ? formatDate(e.end_date) : 'Open'}</td>
                        <td>{e.end_reason ? END_REASON_LABELS[e.end_reason] : '—'}</td>
                        <td>{e.baseline_measure_type ?? '—'}</td>
                        <td className="is-numeric">{e.baseline_score ?? '—'}</td>
                        <td className="nowrap">{formatDate(e.baseline_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

function Figure({
  label,
  value,
  date,
  signed,
}: {
  label: string
  value: number | null
  date?: string | null
  signed?: boolean
}) {
  return (
    <div className="dash__figure">
      <div className="dash__figure-label">{label}</div>
      <div className="dash__figure-value">
        {value === null ? '—' : signed && value > 0 ? `+${value}` : value}
      </div>
      {date !== undefined && <div className="dash__figure-date">{formatDate(date)}</div>}
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="dash__fact">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function SubSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="dash__subsection">
      <h3 className="dash__subsection-title">{title}</h3>
      {children}
    </div>
  )
}

/**
 * Profile entries, grouped by section then sub-field. The API already
 * returns them newest-first within each sub-field, so the first entry is
 * the current value and the rest are its history — the append-only model's
 * display contract (see app/models/profile_entry.py).
 */
function ProfileSections({
  entries,
  patientId,
}: {
  entries: Dashboard['profile_entries']
  patientId: number
}) {
  const grouped = useMemo(() => {
    const bySection = new Map<string, Map<string, Dashboard['profile_entries']>>()
    for (const entry of entries) {
      if (!bySection.has(entry.section)) bySection.set(entry.section, new Map())
      const fields = bySection.get(entry.section)!
      if (!fields.has(entry.sub_field)) fields.set(entry.sub_field, [])
      fields.get(entry.sub_field)!.push(entry)
    }
    return bySection
  }, [entries])

  return (
    <section className="card">
      <div className="card__header">
        <h2 className="card__title">Patient Profile</h2>
        <Link className="btn btn--ghost btn--sm" to={`/patients/${patientId}/profile`}>
          Add entry
        </Link>
      </div>
      <div className="card__body">
        {grouped.size === 0 ? (
          <div className="empty-state">
            <div className="empty-state__title">Nothing recorded yet</div>
            Behavioral health, medical, safety, substance use, and social entries appear here.
          </div>
        ) : (
          <div className="dash__profile">
            {[...grouped.entries()].map(([section, fields]) => (
              <div className="dash__profile-section" key={section}>
                <h3 className="dash__subsection-title">{humanize(section)}</h3>
                <dl className="dash__facts dash__facts--stacked">
                  {[...fields.entries()].map(([subField, values]) => {
                    const [current, ...history] = values
                    return (
                      <div className="dash__fact" key={subField}>
                        <dt>{humanize(subField)}</dt>
                        <dd>
                          {current.value}
                          <span className="dash__profile-meta">
                            {formatDate(current.recorded_date)}
                            {current.recorded_by ? ` · ${current.recorded_by}` : ''}
                          </span>
                          {current.context && (
                            <span className="dash__profile-context">{current.context}</span>
                          )}
                          {history.length > 0 && (
                            <details className="dash__profile-history">
                              <summary>
                                {history.length} earlier {history.length === 1 ? 'entry' : 'entries'}
                              </summary>
                              <ul>
                                {history.map((h) => (
                                  <li key={h.profile_entry_id}>
                                    <span className="dash__profile-meta">
                                      {formatDate(h.recorded_date)}
                                    </span>
                                    {h.value}
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
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

/**
 * Treatment History, merging contacts and consultations into one
 * chronological table — the CTMS's own framing ("includes care manager
 * contacts and case reviews"), with its "BH Contact / Other Contact /
 * Psychiatric Consultation" display grouping.
 */
function TreatmentHistory({
  patientId,
  contacts,
  consultations,
  firstContactDate,
  loading,
}: {
  patientId: number
  contacts: Contact[]
  consultations: Consultation[]
  firstContactDate: string | null
  loading: boolean
}) {
  const rows = useMemo(() => {
    type Row = {
      key: string
      date: string
      type: string
      minutes: number | null
      note: string | null
      detail: string | null
    }
    const contactRows: Row[] = contacts.map((c) => ({
      key: `c-${c.contact_id}`,
      date: c.contact_date,
      type: CONTACT_TYPE_LABELS[c.contact_type],
      minutes: c.duration_minutes,
      note: c.notes,
      detail: [
        c.location ? CONTACT_LOCATION_LABELS[c.location] : null,
        c.attempt_number ? `Attempt #${c.attempt_number}` : null,
        c.discuss_with_psychiatric_consultant ? 'Flagged for consultant' : null,
        c.medications_confirmation
          ? MEDICATION_CONFIRMATION_LABELS[c.medications_confirmation]
          : null,
      ]
        .filter(Boolean)
        .join(' · ') || null,
    }))
    const consultRows: Row[] = consultations.map((c) => ({
      key: `x-${c.consultation_id}`,
      date: c.consultation_date,
      type: 'Psychiatric Consultation',
      minutes: c.duration_minutes,
      note: c.notes,
      detail: c.recommendations_forwarded ? 'Recommendations forwarded' : null,
    }))
    return [...contactRows, ...consultRows].sort((a, b) => b.date.localeCompare(a.date))
  }, [contacts, consultations])

  function weeksInTx(date: string): string {
    if (!firstContactDate) return '—'
    const [fy, fm, fd] = firstContactDate.split('-').map(Number)
    const [ty, tm, td] = date.split('-').map(Number)
    const weeks = Math.floor(
      (Date.UTC(ty, tm - 1, td) - Date.UTC(fy, fm - 1, fd)) / (86_400_000 * 7),
    )
    return weeks < 0 ? '—' : String(weeks)
  }

  return (
    <section className="card">
      <div className="card__header">
        <h2 className="card__title">Treatment History</h2>
        <Link className="btn btn--ghost btn--sm" to={`/patients/${patientId}/contacts`}>
          Open full history
        </Link>
      </div>
      <div className="card__body--flush">
        {loading ? (
          <div className="table-loading">Loading history…</div>
        ) : rows.length === 0 ? (
          <div className="empty-state">No contacts recorded yet.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Type</th>
                <th className="is-numeric">Weeks in Tx</th>
                <th className="is-numeric">Minutes</th>
                <th>Detail</th>
                <th>Note</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key}>
                  <td className="nowrap">{formatDate(row.date)}</td>
                  <td className="nowrap">{row.type}</td>
                  <td className="is-numeric">{weeksInTx(row.date)}</td>
                  <td className="is-numeric">{row.minutes ?? '—'}</td>
                  <td className="text-xs muted">{row.detail ?? '—'}</td>
                  <td className="dash__note-cell">{row.note ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
