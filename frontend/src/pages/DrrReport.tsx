import { useState } from 'react'
import { useApi } from '../api/hooks'
import type { DRRClinicRow } from '../api/types'
import { PageHeader, ReportTimestamp } from '../components/PageHeader'
import { MethodologyNote, RateCell, ReportBody, YearPicker } from '../components/reports'
import '../components/DataTable.css'
import './ActivePatients.css'

/**
 * DRR — Depression Remission or Response, on the HEDIS-style measure.
 *
 * All three rates share one denominator (the full eligible cohort), which is
 * what makes "Follow-Up PHQ-9" worth watching as its own number: a patient
 * who never gets a follow-up assessment counts against remission and
 * response too, rather than being quietly excluded. That convention is
 * deliberate and documented in app/services/drr.py — the note below says so
 * on screen, because a shared denominator is the kind of thing a reader will
 * otherwise assume works the other way.
 */
export function DrrReport() {
  const [year, setYear] = useState(new Date().getFullYear())
  const report = useApi<DRRClinicRow[]>('/reports/drr', { year })
  const rows = report.data ?? []

  const totals = rows.reduce(
    (acc, row) => ({
      index_episode_count: acc.index_episode_count + row.index_episode_count,
      follow_up_phq9_count: acc.follow_up_phq9_count + row.follow_up_phq9_count,
      depression_remission_count: acc.depression_remission_count + row.depression_remission_count,
      depression_response_count: acc.depression_response_count + row.depression_response_count,
    }),
    {
      index_episode_count: 0,
      follow_up_phq9_count: 0,
      depression_remission_count: 0,
      depression_response_count: 0,
    },
  )
  const pct = (count: number) =>
    totals.index_episode_count === 0
      ? 0
      : Math.round((1000 * count) / totals.index_episode_count) / 10

  return (
    <div>
      <PageHeader
        title="Depression Remission or Response"
        subtitle={`Index episodes with a ${year} PHQ-9 baseline`}
        meta={<ReportTimestamp />}
        actions={<YearPicker year={year} onChange={setYear} />}
      />

      <div className="card">
        <div className="table-wrap">
          <ReportBody
            loading={report.loading}
            error={report.error}
            empty={rows.length === 0}
            emptyTitle={`No eligible episodes for ${year} yet`}
            emptyNote="An episode joins this report once its 4-8 month follow-up window has fully closed — before that its outcome is genuinely unknown, so counting it would understate the rates."
          >
            <table className="data-table report-table">
              <thead>
                <tr>
                  <th>Clinic</th>
                  <th className="is-numeric" title="Eligible cohort — the denominator for all three rates">
                    Index episodes
                  </th>
                  <th className="is-numeric" title="A PHQ-9 recorded 4-8 months after baseline">
                    Follow-up PHQ-9
                  </th>
                  <th className="is-numeric" title="Follow-up PHQ-9 under 5">
                    Remission
                  </th>
                  <th className="is-numeric" title="≥50% PHQ-9 reduction from baseline">
                    Response
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.clinic_id}>
                    <td>
                      {row.clinic_id === 'unassigned' ? (
                        <span className="muted">Unassigned</span>
                      ) : (
                        row.clinic_id
                      )}
                    </td>
                    <td className="is-numeric">{row.index_episode_count}</td>
                    <td className="is-numeric">
                      <RateCell
                        count={row.follow_up_phq9_count}
                        denominator={row.index_episode_count}
                        percentage={row.follow_up_phq9_percentage}
                      />
                    </td>
                    <td className="is-numeric">
                      <RateCell
                        count={row.depression_remission_count}
                        denominator={row.index_episode_count}
                        percentage={row.depression_remission_percentage}
                        emphasis
                      />
                    </td>
                    <td className="is-numeric">
                      <RateCell
                        count={row.depression_response_count}
                        denominator={row.index_episode_count}
                        percentage={row.depression_response_percentage}
                        emphasis
                      />
                    </td>
                  </tr>
                ))}
                {rows.length > 1 && (
                  <tr className="data-table__total">
                    <td>All clinics</td>
                    <td className="is-numeric">{totals.index_episode_count}</td>
                    <td className="is-numeric">
                      <RateCell
                        count={totals.follow_up_phq9_count}
                        denominator={totals.index_episode_count}
                        percentage={pct(totals.follow_up_phq9_count)}
                      />
                    </td>
                    <td className="is-numeric">
                      <RateCell
                        count={totals.depression_remission_count}
                        denominator={totals.index_episode_count}
                        percentage={pct(totals.depression_remission_count)}
                        emphasis
                      />
                    </td>
                    <td className="is-numeric">
                      <RateCell
                        count={totals.depression_response_count}
                        denominator={totals.index_episode_count}
                        percentage={pct(totals.depression_response_count)}
                        emphasis
                      />
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </ReportBody>
        </div>

        <MethodologyNote>
          <p>
            <strong>All three rates share one denominator</strong> — the full eligible cohort, not
            just the patients who completed a follow-up. A missed follow-up therefore counts against
            remission and response as well, which is how real HEDIS DRR measures work and what makes
            the follow-up completion rate meaningful on its own.
          </p>
          <p>
            The eligible cohort is index episodes whose PHQ-9 baseline falls in {year}, counted only
            once the 4-8 month follow-up window has fully closed. Remission is a follow-up PHQ-9
            under 5; response is a 50% or greater reduction from baseline. Patients are grouped by
            their current primary clinic.
          </p>
          <p>
            Three differences from the CTMS's own definition are open and unresolved: it builds the
            cohort from the first PHQ-9 of 10 or above in the year regardless of episode, applies an
            age-12-and-over criterion, and includes an episode once four months have elapsed rather
            than once the window closes. Each would move these denominators.
          </p>
        </MethodologyNote>
      </div>
    </div>
  )
}
