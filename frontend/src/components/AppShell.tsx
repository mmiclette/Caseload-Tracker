import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { PROVIDER_ROLE_LABELS } from '../lib/format'
import { PatientSearch } from './PatientSearch'
import './AppShell.css'

/**
 * The application chrome.
 *
 * The CTMS uses a gray menu bar with Patient / Caseload / Tools dropdowns.
 * We keep exactly its information architecture but present it as a left
 * sidebar — the contemporary-SaaS equivalent, and the one structural
 * deviation from the CTMS's layout (CLAUDE.md: "modernize the visual
 * design", "should read as a contemporary SaaS product"). The CTMS's
 * centered patient search keeps its prominent place in the top bar.
 */

interface NavItem {
  to: string
  label: string
  icon: string
}

const CASELOAD_NAV: NavItem[] = [
  { to: '/reminders', label: 'Reminders', icon: '🔔' },
  { to: '/patients', label: 'Active Patients', icon: '📋' },
  { to: '/patients/inactive', label: 'Inactive Patients', icon: '📁' },
]

const REPORT_NAV: NavItem[] = [
  { to: '/reports/caseload-statistics', label: 'Caseload Statistics', icon: '📊' },
  { to: '/reports/quality-metrics', label: 'CoCM Quality Metrics', icon: '📈' },
  { to: '/reports/completed-episodes', label: 'Completed Episodes', icon: '✅' },
  { to: '/reports/drr', label: 'DRR Report', icon: '🎯' },
  { to: '/reports/time-tracker', label: 'Monthly Time Tracker', icon: '⏱️' },
]

export function AppShell() {
  const { provider, signOut } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="shell">
      <aside className="shell__sidebar">
        <div className="shell__brand">
          <span className="shell__brand-mark" aria-hidden="true">
            NF
          </span>
          <span className="shell__brand-text">
            CoCM Registry
            <small>NeuroFlow</small>
          </span>
        </div>

        <nav className="shell__nav" aria-label="Main navigation">
          <NavGroup title="Caseload" items={CASELOAD_NAV} />
          <NavGroup title="Reports" items={REPORT_NAV} />
        </nav>

        <div className="shell__sidebar-footer">
          <button
            type="button"
            className="btn btn--cta shell__new-patient"
            onClick={() => navigate('/patients/new')}
          >
            + New patient
          </button>
        </div>
      </aside>

      <div className="shell__main">
        <header className="shell__topbar">
          <PatientSearch />
          <div className="spacer" />
          {provider && (
            <div className="shell__user">
              <span className="shell__user-name">{provider.name}</span>
              <span className="shell__user-role">{PROVIDER_ROLE_LABELS[provider.role]}</span>
            </div>
          )}
          <button type="button" className="btn btn--ghost" onClick={signOut}>
            Sign out
          </button>
        </header>

        <main className="shell__content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function NavGroup({ title, items }: { title: string; items: NavItem[] }) {
  return (
    <div className="shell__nav-group">
      <div className="shell__nav-title">{title}</div>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end
          className={({ isActive }) =>
            `shell__nav-link${isActive ? ' shell__nav-link--active' : ''}`
          }
        >
          <span className="shell__nav-icon" aria-hidden="true">
            {item.icon}
          </span>
          {item.label}
        </NavLink>
      ))}
    </div>
  )
}
