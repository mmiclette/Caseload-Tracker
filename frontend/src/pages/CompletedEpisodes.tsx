import { useState } from 'react'
import { useApi } from '../api/hooks'
import type { CompletedEpisodeStatistics } from '../api/types'
import { PageHeader, ReportTimestamp } from '../components/PageHeader'
import {
  MethodologyNote,
  RateCell,
  ReportBody,
  StatTile,
  YearPicker,
} from '../components/reports'
import { END_REASON_LABELS, formatNumber, humanize } from '../lib/format'
import '../components/DataTable.css'
import './ActivePatients.css'

/**
 * Completed Episode Statistics — the cohort of episodes closed in a
 * calendar year.
 *
 * The deactivation-reason breakdown deliberately includes a "not recorded"
 * bucket: an episode closed without a reason is a real data-quality signal,
 * and dropping it would quietly overstate how well the program documents
 * outcomes.
 */
export function CompletedEpisodes() {
  const [year, setYear] = useState(new Date().getFullYear())
  const report = useApi<CompletedEpisodeStatistics>('/reports/completed-episode-statistics', {
    year,
  })
  const data = report.data

  const reasonEntries = Object.entries(data?.deactivation_reason_counts ?? {}).sort(
    ([, a], [, b]) => b - a,
  )
  const totalReasons = reasonEntries.reduce((sum, [, count]) => sum + count, 0)

  return (
    <div>
      <PageHeader
        title="Completed Episode Statistics"
        subtitle={`Episodes that closed during ${year}`}
        meta={<ReportTimestamp />}
        actions={<YearPicker year={year} onChange={setYear} />}
      />

      <div className="stack">
        <div className="card">
          <div className="card__body">
            <ReportBody
              loading={report.loading}
              error={report.error}
              empty={!data || data.total_completed_episodes === 0}
              emptyTitle={`No episodes closed in ${year}`}
              emptyNote="Episodes appear here once they have an end date in the selected year."
            >
              {data && (
                <div className="stat-grid">
                  <StatTile label="Completed episodes" value={data.total_completed_episodes} />
                  <StatTile
                    label="Avg weeks in treatment"
                    value={formatNumber(data.avg_weeks_in_treatment)}
                    hint="From episode start to end date"
                  />
                  <StatTile
                    label="Avg contacts per episode"
                    value={formatNumber(data.avg_contacts_per_episode)}
                    hint="Completed contacts; attempts and collaboration excluded"
                  />
                  <StatTile
                    label="With a relapse prevention plan"
                    value={data.relapse_prevention_plan_count}
                    hint="Episodes that recorded at least one RPP contact"
                  />
                </div>
              )}
            </ReportBody>
          </div>
        </div>

        {data && data.total_completed_episodes > 0 && (
          <>
            <div className="card">
              <div className="card__header">
                <h2 className="card__title">Outcomes at episode close</h2>
                <span className="text-xs muted">Baseline vs. most recent same-measure score</span>
              </div>
              <div className="table-wrap">
                <table className="data-table report-table">
                  <thead>
                    <tr>
                      <th>Outcome</th>
                      <th className="is-numeric">Achieved</th>
                      <th>Definition</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Depression response</td>
                      <td className="is-numeric">
                        <RateCell
                          count={data.depression_response_count}
                          denominator={data.depression_response_denominator}
                          percentage={
                            data.depression_response_denominator === 0
                              ? 0
                              : Math.round(
                                  (1000 * data.depression_response_count) /
                                    data.depression_response_denominator,
                                ) / 10
                          }
                          emphasis
                        />
                      </td>
                      <td className="muted text-xs">≥50% PHQ-9 improvement from baseline</td>
                    </tr>
                    <tr>
                      <td>Anxiety improvement</td>
                      <td className="is-numeric">
                        <RateCell
                          count={data.anxiety_improvement_count}
                          denominator={data.anxiety_improvement_denominator}
                          percentage={
                            data.anxiety_improvement_denominator === 0
                              ? 0
                              : Math.round(
                                  (1000 * data.anxiety_improvement_count) /
                                    data.anxiety_improvement_denominator,
                                ) / 10
                          }
                          emphasis
                        />
                      </td>
                      <td className="muted text-xs">≥5-point GAD-7 improvement from baseline</td>
                    </tr>
                    <tr>
                      <td>PTSD improvement</td>
                      <td className="is-numeric">
                        <span
                          className="rate rate--empty"
                          title="PCL-5 has no published improvement threshold in our source material"
                        >
                          <span className="rate__fraction">
                            {data.ptsd_improvement_count} / {data.ptsd_improvement_denominator}
                          </span>
                          <span className="rate__pct">(no threshold)</span>
                        </span>
                      </td>
                      <td className="muted text-xs">
                        PCL-5 threshold unconfirmed — reported as no improvement rather than guessed
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div className="card">
              <div className="card__header">
                <h2 className="card__title">Why episodes ended</h2>
              </div>
              <div className="table-wrap">
                <table className="data-table report-table">
                  <thead>
                    <tr>
                      <th>Reason</th>
                      <th className="is-numeric">Episodes</th>
                      <th className="is-numeric">Share</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reasonEntries.map(([reason, count]) => (
                      <tr key={reason}>
                        <td>
                          {reason === 'not_recorded' ? (
                            <span className="muted">Not recorded</span>
                          ) : (
                            (END_REASON_LABELS[reason as keyof typeof END_REASON_LABELS] ??
                              humanize(reason))
                          )}
                        </td>
                        <td className="is-numeric">{count}</td>
                        <td className="is-numeric">
                          {totalReasons === 0
                            ? '—'
                            : `${Math.round((1000 * count) / totalReasons) / 10}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <MethodologyNote>
                <p>
                  End reasons are deactivation reasons, never clinical outcomes — remission and
                  response are computed by comparing scores, and are shown above. The “not recorded”
                  row counts episodes closed without a reason, kept visible as a data-quality signal
                  rather than dropped.
                </p>
              </MethodologyNote>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
