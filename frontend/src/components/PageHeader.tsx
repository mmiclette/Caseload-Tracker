import type { ReactNode } from 'react'
import './PageHeader.css'

/**
 * The CTMS's full-width title band, modernized: navy bar with the page
 * title on the left and a context card on the right (the CTMS shows either
 * a patient-context card or a report "Export for / Report Created on"
 * card there, depending on the screen).
 */
export function PageHeader({
  title,
  subtitle,
  meta,
  actions,
}: {
  title: string
  subtitle?: ReactNode
  meta?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div className="page-header__band">
        <div className="page-header__titles">
          <h1 className="page-header__title">{title}</h1>
          {subtitle && <div className="page-header__subtitle">{subtitle}</div>}
        </div>
        {meta && <div className="page-header__meta">{meta}</div>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </header>
  )
}

/** The report card's "Report created on" line, matching the CTMS. */
export function ReportTimestamp() {
  const now = new Date()
  return (
    <div className="page-header__timestamp">
      <span className="page-header__timestamp-label">Report created</span>
      <span>
        {now.toLocaleDateString(undefined, {
          weekday: 'long',
          month: 'long',
          day: 'numeric',
          year: 'numeric',
        })}
        {', '}
        {now.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
      </span>
    </div>
  )
}
