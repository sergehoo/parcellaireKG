import { useState } from 'react'
import { changePassword } from '../api/auth'
import { useAuth } from '../auth/AuthContext'

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm odd:bg-slate-50/60">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value || '—'}</dd>
    </div>
  )
}

function PasswordForm() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [msg, setMsg] = useState(null) // {type:'ok'|'err', text}
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setMsg(null)
    if (next !== confirm) {
      setMsg({ type: 'err', text: 'Les deux nouveaux mots de passe ne correspondent pas.' })
      return
    }
    setBusy(true)
    try {
      await changePassword(current, next)
      setMsg({ type: 'ok', text: 'Mot de passe modifié.' })
      setCurrent(''); setNext(''); setConfirm('')
    } catch (err) {
      setMsg({ type: 'err', text: err?.data?.detail || err?.message || 'Échec du changement.' })
    } finally {
      setBusy(false)
    }
  }

  const input = 'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500'
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold text-slate-900">Changer le mot de passe</h2>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Mot de passe actuel</label>
          <input type="password" autoComplete="current-password" required value={current}
            onChange={(e) => setCurrent(e.target.value)} className={input} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Nouveau mot de passe</label>
          <input type="password" autoComplete="new-password" required value={next}
            onChange={(e) => setNext(e.target.value)} className={input} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Confirmer le nouveau mot de passe</label>
          <input type="password" autoComplete="new-password" required value={confirm}
            onChange={(e) => setConfirm(e.target.value)} className={input} />
        </div>
        {msg && (
          <p className={`rounded-lg px-3 py-2 text-sm ${msg.type === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
            {msg.text}
          </p>
        )}
        <button type="submit" disabled={busy}
          className="rounded-lg px-4 py-2 text-sm font-semibold text-white shadow disabled:opacity-60"
          style={{ background: 'var(--kaydan, #ea580c)' }}>
          {busy ? 'Enregistrement…' : 'Mettre à jour'}
        </button>
      </form>
    </div>
  )
}

export default function ProfilePage() {
  const { me } = useAuth()
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

      <PasswordForm />
    </div>
  )
}
