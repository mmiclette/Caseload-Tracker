/**
 * API client.
 *
 * The bearer token lives in module memory only — never localStorage or
 * sessionStorage. CLAUDE.md's PHI rules require patient data to stay in
 * React state and be refetched, and the same reasoning applies to the
 * credential that unlocks it: a token in localStorage survives the tab and
 * is readable by any injected script. The tradeoff is deliberate and
 * visible: a full page reload returns you to the login screen.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

let authToken: string | null = null
let onUnauthorized: (() => void) | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

/** Lets the auth provider clear its own state when a 401 comes back. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

type Params = Record<string, string | number | boolean | null | undefined>

function buildUrl(path: string, params?: Params): string {
  const url = `/api${path}`
  if (!params) return url
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `${url}?${qs}` : url
}

async function request<T>(
  method: 'GET' | 'POST' | 'PATCH',
  path: string,
  options: { params?: Params; body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = {}
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (authToken) headers['Authorization'] = `Bearer ${authToken}`

  const response = await fetch(buildUrl(path, options.params), {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (response.status === 401) {
    onUnauthorized?.()
    throw new ApiError(401, 'Your session has expired. Please sign in again.')
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response))
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/**
 * FastAPI reports errors as {detail: string} for our HTTPExceptions and
 * {detail: [{loc, msg, ...}]} for request-validation failures. Flatten both
 * into one readable sentence.
 */
async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          const entry = item as { loc?: unknown[]; msg?: string }
          const field = Array.isArray(entry.loc) ? entry.loc.slice(1).join('.') : ''
          return field ? `${field}: ${entry.msg ?? 'invalid'}` : (entry.msg ?? 'invalid')
        })
        .join('; ')
    }
  } catch {
    /* fall through to the generic message */
  }
  return `Request failed (${response.status})`
}

export const api = {
  get: <T>(path: string, params?: Params) => request<T>('GET', path, { params }),
  post: <T>(path: string, body: unknown) => request<T>('POST', path, { body }),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, { body }),
}
