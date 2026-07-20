import { useEffect, useState } from 'react'
import { getMe } from '../api/auth'

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm odd:bg-slate-50/60">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value || '—'}</dd>
    </div>
  )
}

export default function ProfilePage() {
  const [me, setMe] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    const c = new AbortController()
    getMe({ signal: c.signal }).then(setMe).catch((e) => { if (e.name !== 'AbortError') setError(e) })
    return () => c.abort()
  }, [])

  if (error) return <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-6 text-rose-700">{error.message}</div>
  if (!me) return <div className="py-20 text-center text-slate-500">Chargement…</div>

  const p = me.profile || {}
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <h1 className="text-2xl font-bold text-slate-900">Mon profil</h1>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center gap-3">
          <span className="flex h-14 w-14 items-center justify-center rounded-full text-lg font-bold text-white"
            style={{ background: 'var(--kaydan)' }}>{me.initials}</span>
          <div className="min-w-0">
            <div className="truncate text-lg font-semibold text-slate-900">{me.full_name}</div>
            <div className="truncate text-sm text-slate-500">{me.email || me.username}</div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {me.is_superuser && <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700">Super-administrateur</span>}
              {me.is_staff && !me.is_superuser && <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-700">Staff</span>}
              {me.permissions?.financial && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">Données financières</span>}
              {me.permissions?.patient && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">Données clients</span>}
            </div>
          </div>
        </div>

        <dl className="overflow-hidden rounded-xl border border-slate-100">
          <Row label="Identifiant" value={me.username} />
          <Row label="Fonction" value={p.job_title} />
          <Row label="Organisation" value={p.organization} />
          <Row label="Département" value={p.department} />
          <Row label="Téléphone" value={p.phone} />
          <Row label="Langue" value={p.language} />
          <Row label="Fuseau horaire" value={p.timezone} />
        </dl>
      </div>

      <div className="flex flex-wrap gap-2">
        <a href="/accounts/password/change/"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">
          Changer le mot de passe
        </a>
        <a href="/accounts/email/"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">
          Gérer mes adresses e-mail
        </a>
      </div>
    </div>
  )
}
