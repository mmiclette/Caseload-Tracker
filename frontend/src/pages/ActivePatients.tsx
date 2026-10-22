import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../api/hooks'
import type { ActivePatientRow, Provider } from '../api/types'
import { PageHeader, ReportTimestamp } from '../components/PageHeader'
import { SortHeader, useSort } from '../components/SortableHeader'
import {
  ConsultationCell,
  Flags,
  FirstScoreCell,
  LastScoreCell,
  ServiceDateCell,
  StatusPill,
} from '../components/cells'
import { PROVIDER_ROLE_LABELS } from '../lib/format'
import '../components/DataTable.css'
import './ActivePatients.css'

/**
 * The Active Patients caseload list — the CTMS's central screen.
 *
 * Column order and grouping are the confirmed CTMS ones (see
 * docs/ctms-reference/README.md): Flags, Patient ID, MRN, Name, Age,
 * Status, Meds, then grouped PHQ-9 / GAD-7 / PCL-5 First+Last, then the
 * Contacts group (I/A, F/U, P/C, RPP), then # Sess, Wks since I/A, and
 * Minutes This Month. Every cell indicator comes from the API.
 */

type SortKey =
  | 'flags'
  | 'patient_id'
  | 'mrn'
  | 'name'
  | 'age'
  | 'status'
  | 'phq9_last'
  | 'gad7_last'
  | 'pcl5_last'
  | 'initial_assessment_date'
  | 'follow_up_date'
  | 'session_count'
  | 'weeks'
  | 'minutes'

export function ActivePatients() {
  const [payer, setPayer] = useState('')
  const [clinicId, setClinicId] = useState('')
  const [providerId, setProviderId] = useState('')

  const params = useMemo(
    () => ({
      payer: payer || undefined,
      clinic_id: clinicId || undefined,
      provider_id: providerId || undefined,
    }),
    [payer, clinicId, providerId],
  )

  const report = useApi<ActivePatientRow[]>('/reports/active-patients', params)
  const providers = useApi<Provider[]>('/providers', { limit: 200 })
  const rows = report.data ?? []

  const { sorted, sort, toggle } = useSort<ActivePatientRow, SortKey>(
    rows,
    {
      flags: (r) =>
        (r.safety_risk ? 4 : 0) + (r.needs_psychiatric_review ? 2 : 0) + (r.custom_flag_active ? 1 : 0),
      patient_id: (r) => r.patient_id,
      mrn: (r) => r.mrn,
      name: (r) => r.name,
      age: (r) => r.age,
      status: (r) => r.status,
      phq9_last: (r) => r.phq9_last,
      gad7_last: (r) => r.gad7_last,
      pcl5_last: (r) => r.pcl5_last,
      initial_assessment_date: (r) => r.initial_assessment_date,
      follow_up_date: (r) => r.follow_up_date,
      session_count: (r) => r.session_count,
      weeks: (r) => r.weeks_since_initial_assessment,
      minutes: (r) => r.minutes_this_month,
    },
    { key: 'flags', direction: 'desc' },
  )

  const careManagers = (providers.data ?? []).filter(
    (p) => p.role === 'care_manager' || p.role === 'psychiatric_consultant' || p.role === 'primary_care_provider',
  )

  return (
    <div>
      <PageHeader
        title="Active Patients"
        subtitle="Current caseload — patients with an open episode of care"
        meta={<ReportTimestamp />}
        actions={
          <>
            <div className="filter">
              <label className="filter__label" htmlFor="filter-provider">
                Report for
              </label>
              <select
                id="filter-provider"
                className="select filter__control"
                value={providerId}
                onChange={(e) => setProviderId(e.target.value)}
              >
                <option value="">My whole program</option>
                {careManagers.map((p) => (
                  <option key={p.provider_id} value={p.provider_id}>
                    {p.name} — {PROVIDER_ROLE_LABELS[p.role]}
                  </option>
                ))}
              </select>
            </div>
            <div className="filter">
              <label className="filter__label" htmlFor="filter-clinic">
                Clinic
              </label>
              <input
                id="filter-clinic"
                className="input filter__control"
                placeholder="All clinics"
                value={clinicId}
                onChange={(e) => setClinicId(e.target.value)}
              />
            </div>
            <div className="filter">
              <label className="filter__label" htmlFor="filter-payer">
                Payer
              </label>
              <input
                id="filter-payer"
                className="input filter__control"
                placeholder="All payers"
                value={payer}
                onChange={(e) => setPayer(e.target.value)}
              />
            </div>
          </>
        }
      />

      {report.error && (
        <div className="error-banner" role="alert">
          {report.error}
        </div>
      )}

      <div className="card">
        <div className="table-wrap">
          {report.loading ? (
            <div className="table-loading">Loading caseload…</div>
          ) : rows.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__title">No patients on this caseload</div>
              Patients appear here once they consent, are enrolled, and have an open episode of
              care.
            </div>
          ) : (
            <table className="data-table caseload">
              <thead>
                <tr className="data-table__group-row">
                  <th colSpan={7} />
                  <th colSpan={2} className="data-table__group-start">
                    PHQ-9
                  </th>
                  <th colSpan={2} className="data-table__group-start">
                    GAD-7
                  </th>
                  <th colSpan={2} className="data-table__group-start">
                    PCL-5
                  </th>
                  <th colSpan={4} className="data-table__group-start">
                    Contacts
                  </th>
                  <th colSpan={3} className="data-table__group-start" />
                </tr>
                <tr>
                  <SortHeader label="Flags" sortKey="flags" sort={sort} onSort={toggle} align="center" />
                  <SortHeader label="Patient ID" sortKey="patient_id" sort={sort} onSort={toggle} />
                  <SortHeader label="MRN" sortKey="mrn" sort={sort} onSort={toggle} />
                  <SortHeader label="Name" sortKey="name" sort={sort} onSort={toggle} />
                  <SortHeader label="Age" sortKey="age" sort={sort} onSort={toggle} align="numeric" />
                  <SortHeader
                    label="Status"
                    sortKey="status"
                    sort={sort}
                    onSort={toggle}
                    align="center"
                    title="T = Treatment · RPP = Relapse Prevention Plan"
                  />
                  <th className="is-center" title="Psychotropic medications prescribed">
                    Meds
                  </th>

                  <th className="is-numeric data-table__group-start" title="First score in the current episode">
                    First
                  </th>
                  <SortHeader label="Last" sortKey="phq9_last" sort={sort} onSort={toggle} align="numeric" title="Most recent score. * = more than 30 days old" />
                  <th className="is-numeric data-table__group-start">First</th>
                  <SortHeader label="Last" sortKey="gad7_last" sort={sort} onSort={toggle} align="numeric" />
                  <th className="is-numeric data-table__group-start">First</th>
                  <SortHeader label="Last" sortKey="pcl5_last" sort={sort} onSort={toggle} align="numeric" />

                  <SortHeader
                    label="I/A"
                    sortKey="initial_assessment_date"
                    sort={sort}
                    onSort={toggle}
                    align="center"
                    title="Initial Assessment date"
                  />
                  <SortHeader
                    label="F/U"
                    sortKey="follow_up_date"
                    sort={sort}
                    onSort={toggle}
                    align="center"
                    title="Most recent Follow-Up date"
                  />
                  <th className="is-center" title="Most recent Psychiatric Consultation">
                    P/C
                  </th>
                  <th className="is-center" title="Most recent Relapse Prevention Plan">
                    R/P
                  </th>

                  <SortHeader label="# Sess" sortKey="session_count" sort={sort} onSort={toggle} align="numeric" title="Completed contacts in the current episode" />
                  <SortHeader label="Wks" sortKey="weeks" sort={sort} onSort={toggle} align="numeric" title="Weeks since the Initial Assessment" />
                  <SortHeader label="Min/mo" sortKey="minutes" sort={sort} onSort={toggle} align="numeric" title="Minutes of service this calendar month" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((row) => (
                  <tr key={row.patient_id}>
                    <td className="is-center">
                      <Flags
                        needsReview={row.needs_psychiatric_review}
                        safetyRisk={row.safety_risk}
                        customActive={row.custom_flag_active}
                        customLabel={row.custom_flag_label}
                      />
                    </td>
                    <td className="tabular muted">
                      {String(row.patient_id).padStart(8, '0')}
                    </td>
                    <td className="tabular">{row.mrn}</td>
                    <td>
                      <Link to={`/patients/${row.patient_id}`} className="caseload__name">
                        {row.name}
                      </Link>
                    </td>
                    <td className="is-numeric">{row.age}</td>
                    <td className="is-center">
                      <StatusPill status={row.status} />
                    </td>
                    <td className="is-center">
                      {row.psychotropic_medications ? (
                        <span className="check-mark" title="Psychotropic medications prescribed">
                          ✓
                        </span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>

                    <td className="is-numeric data-table__group-start">
                      <FirstScoreCell value={row.phq9_first} singleScore={row.phq9_single_score} />
                    </td>
                    <td className="is-numeric">
                      <LastScoreCell
                        value={row.phq9_last}
                        stale={row.phq9_stale}
                        color={row.phq9_last_color}
                      />
                    </td>
                    <td className="is-numeric data-table__group-start">
                      <FirstScoreCell value={row.gad7_first} singleScore={row.gad7_single_score} />
                    </td>
                    <td className="is-numeric">
                      <LastScoreCell value={row.gad7_last} stale={row.gad7_stale} />
                    </td>
                    <td className="is-numeric data-table__group-start">
                      <FirstScoreCell value={row.pcl5_first} singleScore={row.pcl5_single_score} />
                    </td>
                    <td className="is-numeric">
                      <LastScoreCell value={row.pcl5_last} stale={row.pcl5_stale} />
                    </td>

                    <td className="is-center data-table__group-start">
                      <ServiceDateCell
                        date={row.initial_assessment_date}
                        patientId={row.patient_id}
                        quickAddType="initial_assessment"
                      />
                    </td>
                    <td className="is-center">
                      <ServiceDateCell
                        date={row.follow_up_date}
                        patientId={row.patient_id}
                        quickAddType="follow_up"
                      />
                    </td>
                    <td className="is-center">
                      <ConsultationCell value={row.psychiatric_consultation} />
                    </td>
                    <td className="is-center">
                      <ServiceDateCell
                        date={row.relapse_prevention_plan_date}
                        patientId={row.patient_id}
                        quickAddType="relapse_prevention_plan"
                      />
                    </td>

                    <td className="is-numeric">{row.session_count}</td>
                    <td className="is-numeric">
                      {row.weeks_since_initial_assessment ?? <span className="muted">—</span>}
                    </td>
                    <td className="is-numeric">{row.minutes_this_month}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        {rows.length > 0 && (
          <div className="data-table__footer">
            <span>
              {rows.length} {rows.length === 1 ? 'patient' : 'patients'}
            </span>
            <span className="caseload__legend">
              <span className="flag-dot flag-dot--review" /> Needs review
              <span className="flag-dot flag-dot--safety" /> Safety risk
              <span className="flag-dot flag-dot--custom" /> Custom
              <span className="caseload__legend-sep">·</span>* score over 30 days old
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
