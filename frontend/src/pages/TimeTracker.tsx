import { Link } from 'react-router-dom'
import { useApi } from '../api/hooks'
import type { TimeTrackerPatientRow } from '../api/types'
import { PageHeader, ReportTimestamp } from '../components/PageHeader'
import { MethodologyNote, ReportBody } from '../components/reports'
import { formatMonth } from '../lib/format'
import '../components/DataTable.css'
import './ActivePatients.css'

/**
 * Monthly Time Tracker — minutes of service per patient, current month plus
 * the trailing twelve.
 *
 * These are deliberately NOT labelled "billable minutes". The CTMS's own
 * material is explicit that without EHR integration the report lists every
 * recorded minute and "does not distinguish what is billable or not, so
 * providers have to take a look themselves" — calling them billable in the
 * UI would misrepresent them (CLAUDE.md carries this as a standing rule).
 */
export function TimeTracker() {
  const report = useApi<TimeTrackerPatientRow[]>('/reports/time-tracker')
  const rows = report.data ?? []
  const months = rows[0]?.months ?? []

  const monthTotals = months.map((_, index) =>
    rows.reduce((sum, row) => sum + (row.months[index]?.minutes ?? 0), 0),
  )
  const grandTotal = rows.reduce((sum, row) => sum + row.total_minutes, 0)

  // The API returns 404 when the report is switched off for the org, which
  // is a different thing from "no data" and deserves its own message.
  const disabled = report.error !== null && /404|not found/i.test(report.error)

  return (
    <div>
      <PageHeader
        title="Monthly Time Tracker"
        subtitle="Minutes of service per patient — current month and the trailing 12"
        meta={<ReportTimestamp />}
      />

      <div className="card">
        <div className="table-wrap">
          {disabled ? (
            <div className="empty-state">
              <div className="empty-state__title">This report is turned off</div>
              The Monthly Time Tracker is disabled for this program. Enable it in the API
              configuration to use it.
            </div>
          ) : (
            <ReportBody
              loading={report.loading}
              error={report.error}
              empty={rows.length === 0}
              emptyTitle="No recorded minutes in this window"
              emptyNote="A patient appears here once a contact or consultation records a duration."
            >
              <table className="data-table report-table report-table--wide">
                <thead>
                  <tr className="data-table__group-row">
                    <th colSpan={3} />
                    <th colSpan={months.length} className="data-table__group-start">
                      Minutes per month
                    </th>
                    <th />
                  </tr>
                  <tr>
                    <th>Patient ID</th>
                    <th>MRN</th>
                    <th>Name</th>
                    {months.map((month, index) => (
                      <th
                        key={`${month.year}-${month.month}`}
                        className={`is-numeric${index === 0 ? ' data-table__group-start' : ''}`}
                      >
                        {formatMonth(month.year, month.month)}
                      </th>
                    ))}
                    <th className="is-numeric">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.patient_id}>
                      <td className="tabular muted">{String(row.patient_id).padStart(8, '0')}</td>
                      <td className="tabular">{row.mrn}</td>
                      <td>
                        <Link to={`/patients/${row.patient_id}`}>{row.name}</Link>
                      </td>
                      {row.months.map((month, index) => (
                        <td
                          key={`${month.year}-${month.month}`}
                          className={`is-numeric${index === 0 ? ' data-table__group-start' : ''}`}
                        >
                          {month.minutes === 0 ? <span className="muted">0</span> : month.minutes}
                        </td>
                      ))}
                      <td className="is-numeric">
                        <strong>{row.total_minutes}</strong>
                      </td>
                    </tr>
                  ))}
                  <tr className="data-table__total">
                    <td colSpan={3}>All patients</td>
                    {monthTotals.map((total, index) => (
                      <td
                        key={index}
                        className={`is-numeric${index === 0 ? ' data-table__group-start' : ''}`}
                      >
                        {total}
                      </td>
                    ))}
                    <td className="is-numeric">{grandTotal}</td>
                  </tr>
                </tbody>
              </table>
            </ReportBody>
          )}
        </div>

        <MethodologyNote>
          <p>
            Minutes include care manager contacts — care team collaboration among them — plus
            psychiatric consultations. Contact attempts are excluded: outreach that never reached the
            patient is not service time. This matches the “Minutes This Month” column on the
            caseload list exactly.
          </p>
          <p>
            <strong>These are recorded minutes, not billable minutes.</strong> Without EHR
            integration the registry lists every minute entered and cannot tell which are billable —
            that determination is still the provider's to make.
          </p>
          <p>
            A patient appears if they have any recorded minutes in the window, whether or not they
            are still on the caseload, so a patient deactivated part-way through keeps their history
            here.
          </p>
        </MethodologyNote>
      </div>
    </div>
  )
}
