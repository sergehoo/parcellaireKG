import { useState } from 'react'
import { login } from '../api/auth'

// Page de connexion 100 % React (remplace la page HTML allauth). Rendue par
// AuthProvider tant que l'utilisateur n'est pas authentifié : aucune coquille
// Django, aucun flash de carte avant redirection.
export default function LoginPage({ onLoggedIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const me = await login(username.trim(), password)
      onLoggedIn(me)
    } catch (err) {
      setError(err?.data?.detail || err?.message || 'Connexion impossible.')
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl text-lg font-bold text-white"
            style={{ background: 'var(--kaydan, #ea580c)' }}>K</span>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">parcelaireKG</h1>
            <p className="text-sm text-slate-500">Connectez-vous pour continuer</p>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="username" className="mb-1 block text-sm font-medium text-slate-700">
              Nom d'utilisateur
            </label>
            <input
              id="username" name="username" type="text" autoComplete="username" required autoFocus
              value={username} onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-slate-700">
              Mot de passe
            </label>
            <input
              id="password" name="password" type="password" autoComplete="current-password" required
              value={password} onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500"
            />
          </div>

          {error && (
            <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </p>
          )}

          <button
            type="submit" disabled={busy}
            className="w-full rounded-lg px-4 py-2.5 text-sm font-semibold text-white shadow disabled:opacity-60"
            style={{ background: 'var(--kaydan, #ea580c)' }}>
            {busy ? 'Connexion…' : 'Se connecter'}
          </button>
        </form>
      </div>
    </div>
  )
}
