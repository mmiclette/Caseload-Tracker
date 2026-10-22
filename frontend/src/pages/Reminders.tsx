import { Link } from 'react-router-dom'
import { useApi } from '../api/hooks'
import type { Patient, Reminder } from '../api/types'
import { PageHeader } from '../components/PageHeader'
import { SortHeader, useSort } from '../components/SortableHeader'
import { formatDate, humanize } from '../lib/format'
import '../components/DataTable.css'
import './Reminders.css'

/**
 * The Reminders landing page — the first screen a BHCM sees after login, per
 * the CTMS. GET /reminders with no patient_id returns every pending
 * reminder in due-date order.
 *
 * Overdue rows are called out in red because the AIMS guide's whole point
 * for this screen is "patients that are due for an appointment or who may
 * require more intensive efforts to engage them in care" — the days-until
 * number is the actionable content, not decoration.
 */

type SortKey = 'due_date' | 'patient' | 'type'

function daysUntil(iso: string): number {
  const [y, m, d] = iso.split('-').map(Number)
  const due = new Date(y, m - 1, d)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((due.getTime() - today.getTime()) / 86_400_000)
}

function DueCell({ dueDate }: { dueDate: string }) {
  const days = daysUntil(dueDate)
  if (days < 0) {
    return (
      <span className="reminders__due reminders__due--overdue">
        {Math.abs(days)} {Math.abs(days) === 1 ? 'day' : 'days'} overdue
      </span>
    )
  }
  if (days === 0) return <span className="reminders__due reminders__due--today">Due today</span>
  return (
    <span className="reminders__due">
      in {days} {days === 1 ? 'day' : 'days'}
    </span>
  )
}

export function Reminders() {
  const reminders = useApi<Reminder[]>('/reminders')
  const patients = useApi<Patient[]>('/patients', { limit: 500 })

  const patientsById = new Map((patients.data ?? []).map((p) => [p.patient_id, p]))
  const rows = reminders.data ?? []

  const { sorted, sort, toggle } = useSort<Reminder, SortKey>(
    rows,
    {
      due_date: (r) => r.due_date,
      patient: (r) => patientsById.get(r.patient_id)?.name ?? '',
      type: (r) => r.reminder_type,
    },
    { key: 'due_date', direction: 'asc' },
  )

  const overdueCount = rows.filter((r) => daysUntil(r.due_date) < 0).length

  return (
    <div>
      <PageHeader
        title="Reminders"
        subtitle="Patients due for outreach or referral follow-up"
        meta={
          <>
            <div>
              <strong>{rows.length}</strong> pending
            </div>
            {overdueCount > 0 && (
              <div>
                <strong>{overdueCount}</strong> overdue
              </div>
            )}
          </>
        }
      />

      {reminders.error && (
        <div className="error-banner" role="alert">
          {reminders.error}
        </div>
      )}

      <div className="card">
        <div className="table-wrap">
          {reminders.loading ? (
            <div className="table-loading">Loading reminders…</div>
          ) : rows.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__title">Nothing due right now</div>
              Reminders appear here when a patient is due for an appointment or a referral
              follow-up.
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <SortHeader label="Due" sortKey="due_date" sort={sort} onSort={toggle} />
                  <th>When</th>
                  <SortHeader label="Patient" sortKey="patient" sort={sort} onSort={toggle} />
                  <th>MRN</th>
                  <SortHeader label="Reminder" sortKey="type" sort={sort} onSort={toggle} />
                  <th>Notes</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {sorted.map((reminder) => {
                  const patient = patientsById.get(reminder.patient_id)
                  return (
                    <tr key={reminder.reminder_id}>
                      <td className="nowrap">{formatDate(reminder.due_date)}</td>
                      <td className="nowrap">
                        <DueCell dueDate={reminder.due_date} />
                      </td>
                      <td>
                        <Link to={`/patients/${reminder.patient_id}`}>
                          {patient?.name ?? `Patient ${reminder.patient_id}`}
                        </Link>
                      </td>
                      <td className="muted">{patient?.mrn ?? '—'}</td>
                      <td className="nowrap">{humanize(reminder.reminder_type)}</td>
                      <td className="muted">{reminder.notes ?? '—'}</td>
                      <td className="is-center">
                        <Link
                          className="btn btn--secondary btn--sm"
                          to={`/patients/${reminder.patient_id}/contacts/new?type=follow_up`}
                        >
                          Record contact
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
        {rows.length > 0 && (
          <div className="data-table__footer">
            <span>
              {rows.length} pending {rows.length === 1 ? 'reminder' : 'reminders'}
            </span>
            <span>Sorted by due date, soonest first</span>
          </div>
        )}
      </div>
    </div>
  )
}
