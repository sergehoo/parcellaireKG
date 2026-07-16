import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { alertAction, getAlerts } from '../api/analytics'
import { useToast } from '../components/Toasts'
import { levelStyle } from '../lib/criticality'
import { formatDateTime } from '../lib/format'

const LEVELS = [['', 'Tous niveaux'], ['CRITIQUE', 'Critique'], ['ELEVE', 'Élevé'], ['MOYEN', 'Moyen'], ['FAIBLE', 'Faible'], ['INFO', 'Info']]
const STATUSES = [['', 'Actives'], ['NEW', 'Nouvelles'], ['ACK', 'Accusées'], ['RESOLVED', 'Résolues']]

export default function NotificationCenter() {
  const [searchParams, setSearchParams] = useSearchParams()
  const toast = useToast()
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const params = useMemo(() => {
    const p = {}
    for (const [k, v] of searchParams.entries()) p[k] = v
    return p
  }, [searchParams])

  const load = useCallback(() => {
    setLoading(true)
    const controller = new AbortController()
    getAlerts(params, { signal: controller.signal })
      .then((d) => { setPayload(d); setError(null) })
      .catch((err) => { if (err.name !== 'AbortError') setError(err) })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [params])

  useEffect(() => load(), [load])

  function setParam(key, value) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value); else next.delete(key)
    if (key !== 'page') next.delete('page')
    setSearchParams(next)
  }

  async function act(id, action) {
    try {
      await alertAction(id, action)
      toast(action === 'ack' ? 'Alerte accusée.' : action === 'resolve' ? 'Alerte résolue.' : 'Alerte rouverte.', 'success')
      load()
    } catch (err) { toast(err.message, 'error') }
  }

  const c = payload?.counts
  const canManage = payload?.can_manage
  const sel = 'rounded-lg border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-700 shadow-sm focus:border-orange-400 focus:ring-orange-400'

  return (
    <div>
      <Link to="/dashboard" className="text-sm text-slate-500 hover:text-slate-700">← Centre de pilotage</Link>
      <div className="mt-1 mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Centre de notifications</h1>
          <p className="mt-0.5 text-sm text-slate-500">Alertes métier historisées &amp; traçables.</p>
        </div>
        {c && (
          <div className="flex gap-2 text-center text-xs">
            <span className="rounded-lg bg-rose-50 px-2.5 py-1.5 text-rose-700"><b className="text-sm">{c.critique}</b> critiques</span>
            <span className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-slate-700"><b className="text-sm">{c.new}</b> nouvelles</span>
            <span className="rounded-lg bg-sky-50 px-2.5 py-1.5 text-sky-700"><b className="text-sm">{c.ack}</b> accusées</span>
            <span className="rounded-lg bg-emerald-50 px-2.5 py-1.5 text-emerald-700"><b className="text-sm">{c.resolved}</b> résolues</span>
          </div>
        )}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <select value={searchParams.get('level') || ''} onChange={(e) => setParam('level', e.target.value)} className={sel}>
          {LEVELS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select value={searchParams.get('status') || ''} onChange={(e) => setParam('status', e.target.value)} className={sel}>
          {STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        {(searchParams.get('level') || searchParams.get('status')) && (
          <button type="button" onClick={() => setSearchParams({})} className="text-sm text-orange-600 hover:underline">Réinitialiser</button>
        )}
      </div>

      {error && <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error.message}</div>}

      <div className="space-y-2">
        {loading && !payload ? (
          <div className="py-16 text-center text-slate-400">Chargement…</div>
        ) : payload?.results?.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center text-slate-500">Aucune alerte.</div>
        ) : payload?.results?.map((a, i) => {
          const s = levelStyle(a.level)
          return (
            <motion.div key={a.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.02, 0.3) }}
              className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
              <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.dot }} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-slate-800">{a.title}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${s.bg} ${s.text}`}>{s.label}</span>
                  {a.metric && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{a.metric}</span>}
                  {a.status === 'ACK' && <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs text-sky-700">Accusée par {a.acknowledged_by}</span>}
                  {a.status === 'RESOLVED' && <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">Résolue</span>}
                </div>
                {a.detail && <p className="mt-0.5 text-sm text-slate-600">{a.detail}</p>}
                <p className="mt-1 text-xs text-slate-400">
                  {a.program || '—'}{a.lot ? ` · lot ${a.lot}` : ''} · détectée {formatDateTime(a.first_detected_at)}
                </p>
              </div>
              {canManage && (
                <div className="flex shrink-0 flex-col gap-1.5">
                  {a.status === 'NEW' && (
                    <button type="button" onClick={() => act(a.id, 'ack')}
                      className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50">Accuser</button>
                  )}
                  {a.status !== 'RESOLVED' && (
                    <button type="button" onClick={() => act(a.id, 'resolve')}
                      className="rounded-lg border border-emerald-300 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50">Résoudre</button>
                  )}
                  {a.status === 'RESOLVED' && (
                    <button type="button" onClick={() => act(a.id, 'reopen')}
                      className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">Rouvrir</button>
                  )}
                </div>
              )}
            </motion.div>
          )
        })}
      </div>

      {payload && (payload.next || payload.previous) && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <button type="button" disabled={!payload.previous}
            onClick={() => setParam('page', String((Number(searchParams.get('page')) || 1) - 1))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40">← Précédent</button>
          <span className="text-sm text-slate-600">{payload.count} alerte(s)</span>
          <button type="button" disabled={!payload.next}
            onClick={() => setParam('page', String((Number(searchParams.get('page')) || 1) + 1))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40">Suivant →</button>
        </div>
      )}
    </div>
  )
}
