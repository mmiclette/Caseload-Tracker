import { useCallback, useEffect, useState } from 'react'
import { ApiError, api } from './client'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

/**
 * Minimal fetch-on-mount hook. No caching layer on purpose: CLAUDE.md
 * requires patient data to be refetched rather than persisted, so every
 * mount reads fresh from the API. `deps` behaves like a useEffect dep list.
 */
export function useApi<T>(
  path: string | null,
  params?: Record<string, string | number | boolean | null | undefined>,
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(path !== null)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  const paramsKey = JSON.stringify(params ?? {})

  useEffect(() => {
    if (path === null) {
      setData(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .get<T>(path, JSON.parse(paramsKey))
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof ApiError ? err.message : 'Something went wrong.')
        setData(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [path, paramsKey, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, loading, error, reload }
}
