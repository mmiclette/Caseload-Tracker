import { useApi } from '../api/hooks'
import type { QualityMetricsMonth } from '../api/types'
import { PageHeader, ReportTimestamp } from '../components/PageHeader'
import { MethodologyNote, RateCell, ReportBody } from '../components/reports'
import { formatMonth } from '../lib/format'
import '../components/DataTable.css'
import './ActivePatients.css'

/**
 * CoCM Quality Metrics — the rolling 12-month program view.
 *
 * Months are rows, oldest first, matching the API's ordering. Four of the
 * nine documented metrics can't be computed honestly yet and the UI says so
 * rather than showing a number: Caseload Reach has no eligible-population
 * denominator in this data model, and PTSD / pediatric improvement depend
 * on thresholds AIMS has never published, so they always read 0 of their
 * denominator. Showing those as "0%" without explanation would imply a
 * program failing at PTSD care, which would be a lie about the data.
 */
export function QualityMetrics() {
  const report = useApi<QualityMetricsMonth[]>('/reports/quality-metrics')
  const months = report.data ?? []
  const now = new Date()
  const currentKey = `${now.getFullYear()}-${now.getMonth() + 1}`

  return (
    <div>
      <PageHeader
        title="CoCM Quality Metrics"
        subtitle="Program performance for the last 12 months"
        meta={<ReportTimestamp />}
      />

      <div className="card">
        <div className="table-wrap">
          <ReportBody
            loading={report.loading}
            error={report.error}
            empty={months.length === 0}
            emptyTitle="No months to report"
            emptyNote="Metrics appear once patients have episodes open during the reporting window."
          >
            <table className="data-table report-table report-table--wide">
              <thead>
                <tr className="data-table__group-row">
                  <th colSpan={2} />
                  <th colSpan={3} className="data-table__group-start">
                    Process
                  </th>
                  <th colSpan={2} className="data-table__group-start">
                    Adult outcomes
                  </th>
                  <th colSpan={4} className="data-table__group-start">
                    Awaiting confirmed thresholds
                  </th>
                </tr>
                <tr>
                  <th>Month</th>
                  <th className="is-numeric" title="Patients with an episode open during the month">
                    Caseload
                  </th>

                  <th className="is-numeric data-table__group-start" title="Proportion newly enrolled during the period — not computable with this data model">
                    Reach
                  </th>
                  <th className="is-numeric" title="Patients with at least one completed contact">
                    Engagement
                  </th>
                  <th className="is-numeric" title="Patients with at least one completed scale">
                    Measures
                  </th>

                  <th className="is-numeric data-table__group-start" title="50% PHQ-9 improvement from the episode baseline">
                    Depression response
                  </th>
                  <th className="is-numeric" title="5-point GAD-7 improvement from the episode baseline">
                    Anxiety improvement
                  </th>

                  <th className="is-numeric data-table__group-start">PTSD</th>
                  <th className="is-numeric">Ped. anxiety</th>
                  <th className="is-numeric">Ped. depression</th>
                  <th className="is-numeric">Ped. ADHD</th>
                </tr>
              </thead>
              <tbody>
                {months.map((month) => {
                  const isCurrent = `${month.year}-${month.month}` === currentKey
                  return (
                    <tr key={`${month.year}-${month.month}`}>
                      <td
                        className={`report-month${isCurrent ? ' report-month--current' : ''}`}
                      >
                        {formatMonth(month.year, month.month)}
                        {isCurrent && <span className="dash__badge">Current</span>}
                      </td>
                      <td className="is-numeric">{month.caseload_size}</td>

                      <td className="is-numeric">
                        {month.caseload_reach === null ? (
                          <span className="muted" title="Needs an eligible-population denominator this registry has no entity for">
                            n/a
                          </span>
                        ) : (
                          `${month.caseload_reach}%`
                        )}
                      </td>
                      <td className="is-numeric">
                        <RateCell
                          count={month.engagement_count}
                          denominator={month.engagement_denominator}
                          percentage={month.engagement_percentage}
                          emphasis
                        />
                      </td>
                      <td className="is-numeric">
                        <RateCell
                          count={month.measures_completion_count}
                          denominator={month.measures_completion_denominator}
                          percentage={month.measures_completion_percentage}
                        />
                      </td>

                      <td className="is-numeric">
                        <RateCell
                          count={month.depression_response_count}
                          denominator={month.depression_response_denominator}
                          percentage={month.depression_response_percentage}
                          emphasis
                        />
                      </td>
                      <td className="is-numeric">
                        <RateCell
                          count={month.anxiety_improvement_count}
                          denominator={month.anxiety_improvement_denominator}
                          percentage={month.anxiety_improvement_percentage}
                          emphasis
                        />
                      </td>

                      <td className="is-numeric">
                        <UnscoredCell
                          count={month.ptsd_improvement_count}
                          denominator={month.ptsd_improvement_denominator}
                          measure="PCL-5"
                        />
                      </td>
                      <td className="is-numeric">
                        <UnscoredCell
                          count={month.pediatric_anxiety_improvement_count}
                          denominator={month.pediatric_anxiety_improvement_denominator}
                          measure="SCARED"
                        />
                      </td>
                      <td className="is-numeric">
                        <UnscoredCell
                          count={month.pediatric_depression_response_count}
                          denominator={month.pediatric_depression_response_denominator}
                          measure="SMFQ"
                        />
                      </td>
                      <td className="is-numeric">
                        <UnscoredCell
                          count={month.pediatric_adhd_improvement_count}
                          denominator={month.pediatric_adhd_improvement_denominator}
                          measure="Vanderbilt"
                        />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </ReportBody>
        </div>

        <MethodologyNote>
          <p>
            A month's caseload is every patient with an episode open at some point during that
            calendar month, so a patient whose episode closes stops counting in every later month.
          </p>
          <p>
            <strong>Caseload Reach reads “n/a” on purpose.</strong> It needs a count of patients
            eligible for the program, which this registry has no entity for — it only holds patients
            already enrolled. AIMS has not published its own denominator either, so there is nothing
            safe to substitute.
          </p>
          <p>
            <strong>The four right-hand columns will always read 0.</strong> PCL-5, SCARED, SMFQ, and
            Vanderbilt have no published remission or response thresholds in any source we have, so
            the scoring service deliberately reports no improvement for them rather than reusing
            PHQ-9 or GAD-7 cut-offs on scales they were never validated against. The denominators
            are real; the numerators are withheld.
          </p>
          <p>
            Engagement follows the CoCM literature (at least one completed contact in the month).
            Measures Completion and psychiatric case review are this codebase's own reasonable
            extension of concepts the registry tracks, not confirmed AIMS or NCQA methodology.
          </p>
        </MethodologyNote>
      </div>
    </div>
  )
}

function UnscoredCell({
  count,
  denominator,
  measure,
}: {
  count: number
  denominator: number
  measure: string
}) {
  if (denominator === 0) {
    return (
      <span className="muted" title={`No patients tracked on ${measure} this month`}>
        —
      </span>
    )
  }
  return (
    <span
      className="rate rate--empty"
      title={`${denominator} patient(s) tracked on ${measure}, but its improvement threshold is unconfirmed, so no outcome is reported`}
    >
      <span className="rate__fraction">
        {count} / {denominator}
      </span>
      <span className="rate__pct">(no threshold)</span>
    </span>
  )
}
