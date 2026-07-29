import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { getMe, logout as apiLogout } from '../api/auth'
import { setUnauthorizedHandler } from '../api/client'
import LoginPage from '../pages/LoginPage'

const AuthCtx = createContext(null)

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthCtx)
}

function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-300 border-t-orange-500" />
    </div>
  )
}

/**
 * Garde d'authentification du SPA.
 *   - `loading` : on interroge /api/auth/me/ → spinner (plus de flash de carte).
 *   - `anon`    : page de connexion React (aucune page HTML Django).
 *   - `authed`  : l'application (routeur + Layout).
 * Une expiration de session en cours d'usage (401 via client.js) rebascule en
 * `anon` sans rechargement ni redirection vers un template Django.
 */
export function AuthProvider({ children }) {
  const [status, setStatus] = useState('loading')
  const [me, setMe] = useState(null)

  const check = useCallback(async (signal) => {
    try {
      const data = await getMe({ signal })
      setMe(data)
      setStatus('authed')
    } catch (err) {
      if (signal?.aborted) return
      // 401/403 (ou toute erreur au démarrage) → afficher la connexion.
      setMe(null)
      setStatus('anon')
    }
  }, [])

  useEffect(() => {
    const c = new AbortController()
    check(c.signal)
    setUnauthorizedHandler(() => {
      setMe(null)
      setStatus('anon')
    })
    return () => {
      c.abort()
      setUnauthorizedHandler(null)
    }
  }, [check])

  const onLoggedIn = useCallback((data) => {
    setMe(data)
    setStatus('authed')
  }, [])

  const signOut = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      setMe(null)
      setStatus('anon')
    }
  }, [])

  if (status === 'loading') return <FullScreenLoader />
  if (status === 'anon') return <LoginPage onLoggedIn={onLoggedIn} />

  return (
    <AuthCtx.Provider value={{ me, signOut, refresh: () => check() }}>
      {children}
    </AuthCtx.Provider>
  )
}
