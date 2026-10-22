import { Link } from 'react-router-dom'
import type { ActivePatientRow, ContactType, TreatmentStatus } from '../api/types'
import {
  CONTACT_TYPE_LABELS,
  TREATMENT_STATUS_LABELS,
  TREATMENT_STATUS_SHORT,
  formatDate,
} from '../lib/format'

/**
 * Caseload-cell primitives.
 *
 * Every indicator here is computed by the backend (see
 * app/services/reporting.py) — this file only paints. That's deliberate:
 * the 30-day staleness rule and the PHQ-9 red/yellow/green thresholds are
 * clinical rules that must live in scoring.py alone, never re-derived in
 * the UI where they could drift.
 */

/** Patient-level flags: yellow = needs review, red = safety, blue = custom. */
export function Flags({
  needsReview,
  safetyRisk,
  customActive,
  customLabel,
}: {
  needsReview: boolean
  safetyRisk: boolean
  customActive: boolean
  customLabel: string | null
}) {
  const flags: { className: string; title: string }[] = []
  if (needsReview)
    flags.push({ className: 'flag-dot--review', title: 'Flagged for psychiatric review' })
  if (safetyRisk) flags.push({ className: 'flag-dot--safety', title: 'Safety risk' })
  if (customActive)
    flags.push({ className: 'flag-dot--custom', title: customLabel ?? 'Custom flag' })

  if (flags.length === 0) return <span className="muted">—</span>
  return (
    <span className="flags">
      {flags.map((flag) => (
        <span
          key={flag.className}
          className={`flag-dot ${flag.className}`}
          title={flag.title}
          role="img"
          aria-label={flag.title}
        />
      ))}
    </span>
  )
}

export function StatusPill({ status }: { status: TreatmentStatus }) {
  return (
    <span className={`status-pill status-pill--${status}`} title={TREATMENT_STATUS_LABELS[status]}>
      {TREATMENT_STATUS_SHORT[status]}
    </span>
  )
}

/**
 * A measure's First score. Rendered gray when it's the only score on file,
 * matching the CTMS ("Number is gray if only one score has been recorded,
 * meaning First and Last are from the same contact").
 */
export function FirstScoreCell({
  value,
  singleScore,
}: {
  value: number | null
  singleScore: boolean | null
}) {
  if (value === null) return <span className="muted">—</span>
  return (
    <span className={`score-cell ${singleScore ? 'score-cell--single' : 'score-cell--first'}`}>
      {value}
    </span>
  )
}

/**
 * A measure's Last score, with the staleness asterisk and — for PHQ-9 only
 * — the confirmed severity color. GAD-7 and PCL-5 pass no color because the
 * CTMS never documented their rules; they stay neutral rather than reusing
 * PHQ-9's thresholds on a scale they weren't validated for.
 */
export function LastScoreCell({
  value,
  stale,
  color,
}: {
  value: number | null
  stale: boolean | null
  color?: 'red' | 'yellow' | 'green' | null
}) {
  if (value === null) return <span className="muted">—</span>
  const staleTitle = 'Score is more than 30 days old and should be re-administered'
  return (
    <span className={`score-cell${color ? ` score-cell--${color}` : ''}`}>
      {value}
      {stale && (
        <abbr className="score-cell__stale" title={staleTitle}>
          *
        </abbr>
      )}
    </span>
  )
}

/**
 * A service-date cell. The date links to its encounter; an empty cell offers
 * the CTMS's green (+) quick-add for that contact type.
 */
export function ServiceDateCell({
  date,
  patientId,
  quickAddType,
}: {
  date: string | null
  patientId: number
  quickAddType?: ContactType
}) {
  if (date) {
    return (
      <Link to={`/patients/${patientId}/contacts?on=${date}`} className="nowrap">
        {formatDate(date)}
      </Link>
    )
  }
  if (!quickAddType) return <span className="muted">—</span>
  const label = `Record ${CONTACT_TYPE_LABELS[quickAddType].toLowerCase()}`
  return (
    <Link to={`/patients/${patientId}/contacts/new?type=${quickAddType}`} className="quick-add" title={label}>
      +<span className="sr-only">{label}</span>
    </Link>
  )
}

/**
 * The Psychiatric Consultation column: an ISO date, or the literal
 * "CONSIDER" sentinel the backend returns while a patient is flagged and
 * not yet reviewed.
 */
export function ConsultationCell({ value }: { value: ActivePatientRow['psychiatric_consultation'] }) {
  if (value === null) return <span className="muted">—</span>
  if (value === 'CONSIDER') {
    return (
      <span className="consider-badge" title="Flagged for the next Systematic Caseload Review">
        CONSIDER
      </span>
    )
  }
  return <span className="nowrap">{formatDate(value)}</span>
}
