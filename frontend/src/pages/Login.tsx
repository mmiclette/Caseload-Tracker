import { useState } from 'react'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './Login.css'

// Set only by the hosted-prototype build (see Dockerfile). In every other
// build this is undefined, the block below doesn't render, and this file
// behaves exactly as it did before the demo existed.
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === '1'

const DEMO_ACCOUNTS = [
  { label: 'Care manager', detail: '6 active patients', email: 'priya@neuroflow.com' },
  { label: 'Care manager', detail: '3 patients, one flagged', email: 'dana@neuroflow.com' },
  { label: 'Psychiatric consultant', detail: 'case reviews', email: 'ramon@neuroflow.com' },
  { label: 'Supervisor', detail: 'best view of the reports', email: 'demo@neuroflow.com' },
]
const DEMO_PASSWORD = 'demo-password'

export function Login() {
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function signInAs(demoEmail: string) {
    setEmail(demoEmail)
    setPassword(DEMO_PASSWORD)
    setError(null)
    setSubmitting(true)
    try {
      await signIn(demoEmail, DEMO_PASSWORD)
    } catch {
      setError('Could not sign in. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await signIn(email, password)
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? 'Incorrect email or password.'
          : 'Could not sign in. Please try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login">
      <div className="login__panel">
        <div className="login__brand">
          <span className="login__brand-mark" aria-hidden="true">
            NF
          </span>
          <div>
            <div className="login__brand-name">NeuroFlow</div>
            <div className="login__brand-product">Collaborative Care Registry</div>
          </div>
        </div>

        <form className="login__form" onSubmit={onSubmit}>
          <h1 className="login__title">Sign in</h1>
          {error && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}
          <div className="field">
            <label className="field__label" htmlFor="login-email">
              Email
            </label>
            <input
              id="login-email"
              className="input"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              className="input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn--cta login__submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        {DEMO_MODE && (
          <div className="login__demo">
            <div className="login__demo-title">Demo — pick a role to sign in</div>
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.email}
                type="button"
                className="login__demo-account"
                disabled={submitting}
                onClick={() => signInAs(account.email)}
              >
                <span className="login__demo-role">{account.label}</span>
                <span className="login__demo-detail">{account.detail}</span>
              </button>
            ))}
          </div>
        )}

        <p className="login__note">
          {DEMO_MODE
            ? 'Demonstration environment. Every patient, provider and score here is invented — no real patient information is present. Data resets periodically.'
            : 'This registry contains protected health information. Access is limited to authorized members of the care team.'}
        </p>
      </div>
    </div>
  )
}
