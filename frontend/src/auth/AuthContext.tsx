import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, setAuthToken, setUnauthorizedHandler } from '../api/client'
import type { Provider, TokenResponse } from '../api/types'

interface AuthState {
  provider: Provider | null
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [provider, setProvider] = useState<Provider | null>(null)

  const signOut = useCallback(() => {
    setAuthToken(null)
    setProvider(null)
  }, [])

  // A 401 from any request drops us back to the login screen rather than
  // leaving the UI in a half-authenticated state.
  useEffect(() => {
    setUnauthorizedHandler(signOut)
    return () => setUnauthorizedHandler(null)
  }, [signOut])

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.post<TokenResponse>('/auth/login', { email, password })
    setAuthToken(result.access_token)
    setProvider(result.provider)
  }, [])

  const value = useMemo(() => ({ provider, signIn, signOut }), [provider, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
