import { useMemo, useState } from 'react'
import { useApi } from '../api/hooks'
import type { CaseloadStatisticsRow } from '../api/types'
import { PageHeader, ReportTimestamp } from '../components/PageHeader'
import { CountPct, MethodologyNote, RateCell, ReportBody } from '../components/reports'
import { formatNumber } from '../lib/format'
import '../components/DataTable.css'
import './ActivePatients.css'

/**
 * Caseload Statistics.
 *
 * Column list and order are the confirmed CTMS ones
 * (docs/ctms-reference/README.md), with one deliberate difference: the CTMS
 * frames its two outcome columns negatively ("No Response", "No
 * Remission") and we report them positively. Same information, and a
 * positive frame is easier to read next to the per-condition splits.
 *
 * Outcome rates run combined first, then depression, then anxiety, per
 * Matt's 2026-08-07 instruction. Pooling is safe because the
 * primary-diagnosis rule makes the two condition buckets disjoint — every
 * patient counts toward exactly one.
 */

type GroupBy = 'provider' | 'clinic'
type RoleFilter = 'care_manager' | 'psychiatric_consultant' | 'primary_care_provider' | 'all'

const ROLE_FILTERS: { value: RoleFilter; label: string }[] = [
  { value: 'care_manager', label: 'Care managers' },
  { value: 'psychiatric_consultant', label: 'Consultants' },
  { value: 'primary_care_provider', label: 'PCPs' },
  { value: 'all', label: 'All roles' },
]

/**
 * The endpoint returns one row per provider who currently has patients,
 * whatever their role, and the role is carried in group_label's suffix
 * ("Priya Nandakumar (care_manager)"). CLAUDE.md's design note is explicit
 * that a per-consultant or per-PCP view is this same report filtered
 * client-side on that suffix rather than a separate endpoint mode — so
 * that's what this does.
 *
 * It defaults to care managers, matching the CTMS's own "Care Manager"
 * column header, and because mixing roles makes the summary row
 * meaningless: the same patient appears under their care manager, their
 * consultant, and their PCP, so an all-roles total counts them three times.
 */
function roleOf(row: CaseloadStatisticsRow): string | null {
  return /\(([a-z_]+)\)\s*$/.exec(row.group_label)?.[1] ?? null
}

function labelWithoutRole(row: CaseloadStatisticsRow): string {
  return row.group_label.replace(/\s*\([a-z_]+\)\s*$/, '')
}

export function CaseloadStatistics() {
  const [groupBy, setGroupBy] = useState<GroupBy>('provider')
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('care_manager')
  const report = useApi<CaseloadStatisticsRow[]>('/reports/caseload-statistics', {
    group_by: groupBy,
  })
  const allRows = report.data ?? []
  const rows = useMemo(
    () =>
      groupBy === 'clinic' || roleFilter === 'all'
        ? allRows
        : allRows.filter((row) => roleOf(row) === roleFilter),
    [allRows, groupBy, roleFilter],
  )
  const mixingRoles = groupBy === 'provider' && roleFilter === 'all'

  /**
   * The CTMS shows an "All" row. Summing group rows is the only way to get
   * one without a new endpoint, so counts are summed and percentages
   * recomputed from those sums — never averaged. A patient assigned to two
   * providers (or two clinics) counts in each group, so this row can exceed
   * the distinct patient count; the note below says so.
   */
  const total = useMemo(() => {
    if (rows.length === 0) return null
    const sum = (pick: (r: CaseloadStatisticsRow) => number) => rows.reduce((a, r) => a + pick(r), 0)
    const pct = (count: number, denom: number) =>
      denom === 0 ? 0 : Math.round((1000 * count) / denom) / 10
    const caseload = sum((r) => r.caseload_size)
    const weightedAvg = (pick: (r: CaseloadStatisticsRow) => number | null) => {
      const contributing = rows.filter((r) => pick(r) !== null && r.caseload_size > 0)
      const weight = contributing.reduce((a, r) => a + r.caseload_size, 0)
      if (weight === 0) return null
      return (
        Math.round(
          (10 * contributing.reduce((a, r) => a + (pick(r) as number) * r.caseload_size, 0)) / weight,
        ) / 10
      )
    }
    // Outcome rates need their percentages recomputed from the summed
    // count/denominator pairs — averaging the per-group percentages would
    // weight a one-patient group the same as a fifty-patient one.
    const rate = (
      countPick: (r: CaseloadStatisticsRow) => number,
      denomPick: (r: CaseloadStatisticsRow) => number,
    ) => {
      const count = sum(countPick)
      const denominator = sum(denomPick)
      return { count, denominator, percentage: pct(count, denominator) }
    }
    const combinedResponse = rate((r) => r.combined_response_count, (r) => r.combined_response_denominator)
    const combinedRemission = rate((r) => r.combined_remission_count, (r) => r.combined_remission_denominator)
    const depResponse = rate((r) => r.depression_response_count, (r) => r.depression_response_denominator)
    const depRemission = rate((r) => r.depression_remission_count, (r) => r.depression_remission_denominator)
    const anxResponse = rate((r) => r.anxiety_response_count, (r) => r.anxiety_response_denominator)
    const anxRemission = rate((r) => r.anxiety_remission_count, (r) => r.anxiety_remission_denominator)

    return {
      caseload_size: caseload,
      patients_with_contact_count: sum((r) => r.patients_with_contact_count),
      patients_with_contact_percentage: pct(sum((r) => r.patients_with_contact_count), caseload),
      avg_visits_per_patient: weightedAvg((r) => r.avg_visits_per_patient) ?? 0,
      avg_session_duration_minutes: weightedAvg((r) => r.avg_session_duration_minutes),
      pct_contacts_with_completed_scale: weightedAvg((r) => r.pct_contacts_with_completed_scale) ?? 0,
      rpp_count: sum((r) => r.rpp_count),
      rpp_percentage: pct(sum((r) => r.rpp_count), caseload),
      flagged_count: sum((r) => r.flagged_count),
      flagged_percentage: pct(sum((r) => r.flagged_count), caseload),
      with_consultation_count: sum((r) => r.with_consultation_count),
      with_consultation_percentage: pct(sum((r) => r.with_consultation_count), caseload),
      not_improving_without_consultation_count: sum(
        (r) => r.not_improving_without_consultation_count,
      ),
      avg_phq9_first: weightedAvg((r) => r.avg_phq9_first),
      avg_phq9_last: weightedAvg((r) => r.avg_phq9_last),
      avg_gad7_first: weightedAvg((r) => r.avg_gad7_first),
      avg_gad7_last: weightedAvg((r) => r.avg_gad7_last),
      combined_response_count: combinedResponse.count,
      combined_response_denominator: combinedResponse.denominator,
      combined_response_percentage: combinedResponse.percentage,
      combined_remission_count: combinedRemission.count,
      combined_remission_denominator: combinedRemission.denominator,
      combined_remission_percentage: combinedRemission.percentage,
      depression_response_count: depResponse.count,
      depression_response_denominator: depResponse.denominator,
      depression_response_percentage: depResponse.percentage,
      depression_remission_count: depRemission.count,
      depression_remission_denominator: depRemission.denominator,
      depression_remission_percentage: depRemission.percentage,
      anxiety_response_count: anxResponse.count,
      anxiety_response_denominator: anxResponse.denominator,
      anxiety_response_percentage: anxResponse.percentage,
      anxiety_remission_count: anxRemission.count,
      anxiety_remission_denominator: anxRemission.denominator,
      anxiety_remission_percentage: anxRemission.percentage,
    }
  }, [rows])

  return (
    <div>
      <PageHeader
        title="Caseload Statistics"
        subtitle="Population-level metrics for patients currently in treatment"
        meta={<ReportTimestamp />}
        actions={
          <>
            <div className="filter">
              <span className="filter__label">Aggregate by</span>
              <div className="segmented" role="group" aria-label="Aggregate by">
                {(['provider', 'clinic'] as GroupBy[]).map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={`segmented__option${groupBy === option ? ' segmented__option--active' : ''}`}
                    onClick={() => setGroupBy(option)}
                  >
                    {option === 'provider' ? 'Provider' : 'Clinic'}
                  </button>
                ))}
              </div>
            </div>
            {groupBy === 'provider' && (
              <div className="filter">
                <label className="filter__label" htmlFor="role-filter">
                  Role
                </label>
                <select
                  id="role-filter"
                  className="select filter__control"
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value as RoleFilter)}
                >
                  {ROLE_FILTERS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </>
        }
      />

      <div className="card">
        <div className="table-wrap">
          <ReportBody
            loading={report.loading}
            error={report.error}
            empty={rows.length === 0}
            emptyTitle="No caseload to report on"
            emptyNote="Groups appear here once patients are assigned to a provider or clinic and have an open episode."
          >
            <table className="data-table report-table report-table--wide">
              <thead>
                <tr className="data-table__group-row">
                  <th colSpan={2} />
                  <th colSpan={3} className="data-table__group-start">
                    Care manager contacts
                  </th>
                  <th colSpan={4} className="data-table__group-start">
                    Psychiatric consultation
                  </th>
                  <th colSpan={4} className="data-table__group-start">
                    Average scores
                  </th>
                  <th colSpan={2} className="data-table__group-start">
                    Combined outcomes
                  </th>
                  <th colSpan={2} className="data-table__group-start">
                    Depression
                  </th>
                  <th colSpan={2} className="data-table__group-start">
                    Anxiety
                  </th>
                </tr>
                <tr>
                  <th>{groupBy === 'provider' ? 'Provider' : 'Clinic'}</th>
                  <th className="is-numeric" title="Patients currently in treatment">
                    Caseload
                  </th>

                  <th className="is-numeric data-table__group-start" title="Patients with at least one completed contact this episode">
                    Pts w/ contact
                  </th>
                  <th className="is-numeric" title="Average completed contacts per patient">
                    Avg visits
                  </th>
                  <th className="is-numeric" title="Proportion of contacts with a completed scale">
                    W/ scale
                  </th>

                  <th className="is-numeric data-table__group-start" title="Patients in relapse prevention plan status">
                    In R/P
                  </th>
                  <th className="is-numeric" title="Patients currently flagged for review">
                    Flagged
                  </th>
                  <th className="is-numeric" title="Patients with a consultation this episode">
                    W/ P/C
                  </th>
                  <th className="is-numeric" title="Not improving and not reviewed in the past two months">
                    Not impr. w/o P/C
                  </th>

                  <th className="is-numeric data-table__group-start">PHQ first</th>
                  <th className="is-numeric">PHQ last</th>
                  <th className="is-numeric">GAD first</th>
                  <th className="is-numeric">GAD last</th>

                  <th className="is-numeric data-table__group-start">Response</th>
                  <th className="is-numeric">Remission</th>
                  <th className="is-numeric data-table__group-start">Response</th>
                  <th className="is-numeric">Remission</th>
                  <th className="is-numeric data-table__group-start">Response</th>
                  <th className="is-numeric">Remission</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <StatsRow
                    key={`${row.group_type}-${row.group_key}`}
                    row={row}
                    label={groupBy === 'provider' ? labelWithoutRole(row) : row.group_label}
                  />
                ))}
                {total && rows.length > 1 && !mixingRoles && (
                  <StatsRow row={total as CaseloadStatisticsRow} label="All groups" isTotal />
                )}
              </tbody>
            </table>
          </ReportBody>
        </div>

        <MethodologyNote>
          <p>
            Every figure covers each patient's currently open episode — “current caseload” means
            what is happening now, not lifetime history. Percentages in the caseload columns use the
            caseload size as their denominator.
          </p>
          <p>
            Outcome rates follow the primary diagnosis: a patient counts toward exactly one
            condition's rates, on the measure that diagnosis maps to (depression → PHQ-9, anxiety →
            GAD-7). Combined pools those two disjoint buckets. Patients whose measure has no
            confirmed threshold — PCL-5 and the pediatric scales — are excluded from these rates
            rather than counted as failures. “Not improving without P/C” uses a two-month review
            window.
          </p>
          {rows.length > 1 && !mixingRoles && (
            <p>
              The “All groups” row sums the rows above and recomputes each percentage from those
              sums. A patient assigned to more than one {groupBy} counts in each, so this row can
              exceed the number of distinct patients.
            </p>
          )}
          {mixingRoles && (
            <p>
              <strong>Showing every role at once, so there is no summary row.</strong> A patient
              appears under their care manager, their psychiatric consultant, and their primary care
              provider, so totalling these rows would count most patients two or three times. Pick a
              single role to get a meaningful total.
            </p>
          )}
        </MethodologyNote>
      </div>
    </div>
  )
}

function StatsRow({
  row,
  label,
  isTotal,
}: {
  row: CaseloadStatisticsRow
  label: string
  isTotal?: boolean
}) {
  return (
    <tr className={isTotal ? 'data-table__total' : undefined}>
      <td className="nowrap">{label}</td>
      <td className="is-numeric">{row.caseload_size}</td>

      <td className="is-numeric data-table__group-start">
        <CountPct count={row.patients_with_contact_count} percentage={row.patients_with_contact_percentage} />
      </td>
      <td className="is-numeric">{row.avg_visits_per_patient}</td>
      <td className="is-numeric">{row.pct_contacts_with_completed_scale}%</td>

      <td className="is-numeric data-table__group-start">
        <CountPct count={row.rpp_count} percentage={row.rpp_percentage} />
      </td>
      <td className="is-numeric">
        <CountPct count={row.flagged_count} percentage={row.flagged_percentage} />
      </td>
      <td className="is-numeric">
        <CountPct count={row.with_consultation_count} percentage={row.with_consultation_percentage} />
      </td>
      <td className="is-numeric">{row.not_improving_without_consultation_count}</td>

      <td className="is-numeric data-table__group-start">{formatNumber(row.avg_phq9_first)}</td>
      <td className="is-numeric">{formatNumber(row.avg_phq9_last)}</td>
      <td className="is-numeric">{formatNumber(row.avg_gad7_first)}</td>
      <td className="is-numeric">{formatNumber(row.avg_gad7_last)}</td>

      <td className="is-numeric data-table__group-start">
        <RateCell
          count={row.combined_response_count}
          denominator={row.combined_response_denominator}
          percentage={row.combined_response_percentage ?? 0}
          emphasis
        />
      </td>
      <td className="is-numeric">
        <RateCell
          count={row.combined_remission_count}
          denominator={row.combined_remission_denominator}
          percentage={row.combined_remission_percentage ?? 0}
          emphasis
        />
      </td>
      <td className="is-numeric data-table__group-start">
        <RateCell
          count={row.depression_response_count}
          denominator={row.depression_response_denominator}
          percentage={row.depression_response_percentage ?? 0}
        />
      </td>
      <td className="is-numeric">
        <RateCell
          count={row.depression_remission_count}
          denominator={row.depression_remission_denominator}
          percentage={row.depression_remission_percentage ?? 0}
        />
      </td>
      <td className="is-numeric data-table__group-start">
        <RateCell
          count={row.anxiety_response_count}
          denominator={row.anxiety_response_denominator}
          percentage={row.anxiety_response_percentage ?? 0}
        />
      </td>
      <td className="is-numeric">
        <RateCell
          count={row.anxiety_remission_count}
          denominator={row.anxiety_remission_denominator}
          percentage={row.anxiety_remission_percentage ?? 0}
        />
      </td>
    </tr>
  )
}
