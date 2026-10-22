import type { ReactNode } from 'react'
import './reports.css'

/**
 * Shared report primitives.
 *
 * Every rate in the API arrives as a count, a denominator, and a
 * percentage. RateCell renders all three the way the CTMS reports do
 * ("4 / 4" over "(100%)"), and — importantly — renders an em dash when the
 * denominator is zero rather than a misleading 0%. A rate with no
 * denominator isn't zero, it's unmeasurable, and the CTMS makes the same
 * distinction ("– / 0  (–%)").
 */
export function RateCell({
  count,
  denominator,
  percentage,
  emphasis,
}: {
  count: number
  denominator: number
  percentage: number
  emphasis?: boolean
}) {
  if (denominator === 0) {
    return (
      <span className="rate rate--empty" title="No patients met the criteria for this rate yet">
        <span className="rate__fraction">— / 0</span>
        <span className="rate__pct">(—)</span>
      </span>
    )
  }
  return (
    <span className={`rate${emphasis ? ' rate--emphasis' : ''}`}>
      <span className="rate__fraction">
        {count} / {denominator}
      </span>
      <span className="rate__pct">({percentage}%)</span>
    </span>
  )
}

/** A count with its percentage of a stated denominator, as the CTMS shows. */
export function CountPct({ count, percentage }: { count: number; percentage: number }) {
  return (
    <span className="rate">
      <span className="rate__fraction">{count}</span>
      <span className="rate__pct">({percentage}%)</span>
    </span>
  )
}

export function StatTile({
  label,
  value,
  hint,
}: {
  label: string
  value: ReactNode
  hint?: string
}) {
  return (
    <div className="stat-tile">
      <div className="stat-tile__label">{label}</div>
      <div className="stat-tile__value">{value}</div>
      {hint && <div className="stat-tile__hint">{hint}</div>}
    </div>
  )
}

/**
 * A methodology note. Every report in this codebase has at least one
 * documented assumption or unmeasurable metric; surfacing it in the UI
 * keeps a number from being read as more confirmed than it is.
 */
export function MethodologyNote({ children }: { children: ReactNode }) {
  return (
    <div className="methodology">
      <span className="methodology__label">How this is calculated</span>
      <div className="methodology__body">{children}</div>
    </div>
  )
}

export function YearPicker({
  year,
  onChange,
  label = 'Year',
}: {
  year: number
  onChange: (year: number) => void
  label?: string
}) {
  const current = new Date().getFullYear()
  const years = Array.from({ length: 6 }, (_, i) => current - i)
  return (
    <div className="filter">
      <label className="filter__label" htmlFor="report-year">
        {label}
      </label>
      <select
        id="report-year"
        className="select filter__control"
        value={year}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>
    </div>
  )
}

export function ReportBody({
  loading,
  error,
  empty,
  emptyTitle,
  emptyNote,
  children,
}: {
  loading: boolean
  error: string | null
  empty: boolean
  emptyTitle: string
  emptyNote: string
  children: ReactNode
}) {
  if (error) {
    return (
      <div className="error-banner" role="alert">
        {error}
      </div>
    )
  }
  if (loading) return <div className="table-loading">Generating report…</div>
  if (empty) {
    return (
      <div className="empty-state">
        <div className="empty-state__title">{emptyTitle}</div>
        {emptyNote}
      </div>
    )
  }
  return <>{children}</>
}
