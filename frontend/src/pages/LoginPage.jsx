import { useState } from 'react'
import { login } from '../api/auth'

// Page de connexion 100 % React (remplace la page HTML allauth). Rendue par
// AuthProvider tant que l'utilisateur n'est pas authentifié : aucune coquille
// Django, aucun flash de carte avant redirection.

const FEATURES = [
  {
    title: 'Carte parcellaire interactive',
    text: 'Lots, statuts de vente et orthophotos haute résolution sur un même écran.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75 3.75 9v11.25L9 18m0-11.25 6 2.25m-6-2.25V18m6-9 5.25-2.25V18L15 20.25m0-11.25v11.25m0 0L9 18" />
      </svg>
    ),
  },
  {
    title: 'Suivi financier en temps réel',
    text: 'Encaissements CRM, avancement travaux et écarts de paiement consolidés.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125C16.5 3.504 17.004 3 17.625 3h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
      </svg>
    ),
  },
  {
    title: 'Alertes automatiques',
    text: 'Rapports PDF et notifications e-mail dès qu’un seuil critique est franchi.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
        <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 0 0 5.454-1.31A8.967 8.967 0 0 1 18 9.75V9A6 6 0 0 0 6 9v.75a8.967 8.967 0 0 1-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 0 1-5.714 0m5.714 0a3 3 0 1 1-5.714 0" />
      </svg>
    ),
  },
]

// Message précis selon l'échec : un libellé générique cache la vraie cause
// (CSRF/domaine non autorisé vs identifiants faux vs serveur injoignable).
function errorMessage(err) {
  if (err?.status === 429) {
    return err?.data?.detail
      || 'Trop de tentatives : compte temporairement verrouillé. Réessayez dans une quinzaine de minutes.'
  }
  if (err?.status === 403) {
    return 'Échec de la vérification de sécurité (CSRF). Si le problème persiste, '
      + 'ce domaine n’est probablement pas autorisé côté serveur '
      + '(ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS) — contactez l’administrateur.'
  }
  if (err?.status >= 500) {
    return 'Le serveur a rencontré une erreur. Réessayez dans un instant.'
  }
  if (err?.data?.detail || err?.message) {
    // TypeError de fetch = réseau coupé / serveur injoignable.
    if (err.name === 'TypeError') return 'Serveur injoignable. Vérifiez votre connexion internet.'
    return err?.data?.detail || err.message
  }
  return 'Connexion impossible.'
}

export default function LoginPage({ onLoggedIn }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
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
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  const inputClass =
    'w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 ' +
    'placeholder:text-slate-400 outline-none transition focus:border-orange-500 focus:ring-2 focus:ring-orange-500/30'

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* ------- Panneau marque (caché sur mobile) ------- */}
      <aside className="relative hidden w-[46%] flex-col justify-between overflow-hidden bg-slate-900 p-10 text-white lg:flex xl:p-14">
        {/* Trame « parcellaire » décorative */}
        <svg aria-hidden="true" className="absolute inset-0 h-full w-full opacity-[0.07]">
          <defs>
            <pattern id="parcels" width="56" height="56" patternUnits="userSpaceOnUse">
              <path d="M56 0H0v56" fill="none" stroke="white" strokeWidth="1" />
              <path d="M28 0v28H0" fill="none" stroke="white" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#parcels)" />
        </svg>
        {/* Halo orange */}
        <div aria-hidden="true" className="absolute -left-32 -top-32 h-96 w-96 rounded-full blur-3xl"
          style={{ background: 'radial-gradient(closest-side, rgba(234,88,12,.45), transparent)' }} />
        <div aria-hidden="true" className="absolute -bottom-40 -right-24 h-96 w-96 rounded-full blur-3xl"
          style={{ background: 'radial-gradient(closest-side, rgba(234,88,12,.25), transparent)' }} />

        <div className="relative flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl text-lg font-bold shadow-lg"
            style={{ background: 'var(--kaydan, #ea580c)' }}>K</span>
          <div>
            <p className="text-lg font-semibold leading-tight">Parcellaire KG</p>
            <p className="text-xs uppercase tracking-widest text-orange-300/90">Kaydan Groupe</p>
          </div>
        </div>

        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold leading-snug xl:text-4xl">
            Le foncier, les ventes et la construction, <span className="text-orange-400">sur une seule carte</span>.
          </h2>
          <ul className="mt-8 space-y-5">
            {FEATURES.map((f) => (
              <li key={f.title} className="flex items-start gap-3.5">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/10 text-orange-300">
                  {f.icon}
                </span>
                <div>
                  <p className="text-sm font-semibold">{f.title}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-slate-300">{f.text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-slate-400">
          © {new Date().getFullYear()} Kaydan Groupe — plateforme interne de gestion parcellaire.
        </p>
      </aside>

      {/* ------- Formulaire ------- */}
      <main className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-sm">
          {/* En-tête compact (sert aussi de marque sur mobile) */}
          <div className="mb-8 flex flex-col items-center gap-3 text-center lg:items-start lg:text-left">
            <span className="flex h-12 w-12 items-center justify-center rounded-xl text-lg font-bold text-white shadow-md lg:hidden"
              style={{ background: 'var(--kaydan, #ea580c)' }}>K</span>
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">Bon retour 👋</h1>
              <p className="mt-1 text-sm text-slate-500">Connectez-vous à votre espace Parcellaire KG.</p>
            </div>
          </div>

          <form onSubmit={submit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="username" className="mb-1.5 block text-sm font-medium text-slate-700">
                Nom d&apos;utilisateur
              </label>
              <input
                id="username" name="username" type="text" autoComplete="username" required autoFocus
                placeholder="ex. s.ogah"
                value={username} onChange={(e) => setUsername(e.target.value)}
                className={inputClass}
              />
            </div>

            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700">
                Mot de passe
              </label>
              <div className="relative">
                <input
                  id="password" name="password" required
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  onKeyUp={(e) => setCapsLock(e.getModifierState && e.getModifierState('CapsLock'))}
                  className={inputClass + ' pr-11'}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-slate-400 transition hover:text-slate-600"
                >
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.964-7.178Z" />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                    </svg>
                  )}
                </button>
              </div>
              {capsLock && (
                <p className="mt-1.5 text-xs font-medium text-amber-600">⇪ Verrouillage majuscules activé</p>
              )}
            </div>

            {error && (
              <div role="alert" className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-700">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="mt-0.5 h-4.5 w-4.5 shrink-0" style={{ width: 18, height: 18 }}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                </svg>
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit" disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-orange-600/25 transition hover:brightness-110 active:scale-[0.99] disabled:opacity-60 disabled:hover:brightness-100"
              style={{ background: 'var(--kaydan, #ea580c)' }}
            >
              {busy && (
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z" />
                </svg>
              )}
              {busy ? 'Connexion en cours…' : 'Se connecter'}
            </button>

            <p className="pt-1 text-center text-xs text-slate-400">
              Mot de passe oublié ? Contactez votre administrateur Kaydan.
            </p>
          </form>
        </div>
      </main>
    </div>
  )
}
