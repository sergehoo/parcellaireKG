import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getAtRisk } from '../api/analytics'
import useReferenceData from '../hooks/useReferenceData'
import { levelStyle } from '../lib/criticality'
import { formatDate } from '../lib/format'

const LEVEL_OPTS = [
  { value: '', label: 'Tous les niveaux' },
  { value: 'CRITIQUE', label: 'Critique' },
  { value: 'ELEVE', label: 'Élevé' },
  { value: 'MOYEN', label: 'Moyen' },
  { value: 'FAIBLE', label: 'Conforme' },
  { value: 'INFO', label: 'Construction en avance' },
]

export default function AtRiskPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { refData } = useReferenceData()
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const params = useMemo(() => {
    const p = {}
    for (const [key, v] of searchParams.entries()) p[key] = v
    return p
  }, [searchParams])

  const load = useCallback(() => {
    setLoading(true)
    const controller = new AbortController()
    getAtRisk(params, { signal: controller.signal })
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

  const sel = 'rounded-lg border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-700 shadow-sm focus:border-orange-400 focus:ring-orange-400'

  return (
    <div>
      <Link to="/dashboard" className="text-sm text-slate-500 hover:text-slate-700">← Centre de pilotage</Link>
      <div className="mt-1 mb-5">
        <h1 className="text-2xl font-bold text-slate-900">Clients à risque</h1>
        <p className="mt-0.5 text-sm text-slate-500">
          Classement par IDCP (paiement − construction). {payload ? `${payload.count} dossier(s).` : ''}
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <select value={searchParams.get('level') || ''} onChange={(e) => setParam('level', e.target.value)} className={sel}>
          {LEVEL_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select value={searchParams.get('program') || ''} onChange={(e) => setParam('program', e.target.value)} className={sel}>
          <option value="">Tous les programmes</option>
          {refData?.programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={searchParams.get('min_idcp') || ''} onChange={(e) => setParam('min_idcp', e.target.value)} className={sel}>
          <option value="">IDCP min</option>
          <option value="10">≥ 10 %</option>
          <option value="20">≥ 20 %</option>
          <option value="40">≥ 40 %</option>
        </select>
        {(searchParams.get('level') || searchParams.get('program') || searchParams.get('min_idcp')) && (
          <button type="button" onClick={() => setSearchParams({})} className="text-sm text-orange-600 hover:underline">Réinitialiser</button>
        )}
      </div>

      {error && <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error.message}</div>}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-600">
              <tr>
                <th className="px-3 py-2.5">Client</th>
                <th className="px-3 py-2.5">Programme</th>
                <th className="px-3 py-2.5">Lot</th>
                <th className="px-3 py-2.5 text-right">Montant payé</th>
                <th className="px-3 py-2.5 text-right">% payé</th>
                <th className="px-3 py-2.5 text-right">Construction</th>
                <th className="px-3 py-2.5 text-right">Écart (IDCP)</th>
                <th className="px-3 py-2.5">Commercial</th>
                <th className="px-3 py-2.5">Vente</th>
                <th className="px-3 py-2.5">Niveau</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && !payload ? (
                <tr><td colSpan={10} className="px-4 py-16 text-center text-slate-400">Chargement…</td></tr>
              ) : payload?.results?.length === 0 ? (
                <tr><td colSpan={10} className="px-4 py-16 text-center text-slate-500">Aucun dossier.</td></tr>
              ) : payload?.results?.map((r) => {
                const s = levelStyle(r.level)
                return (
                  <tr key={r.sale_id} className="hover:bg-orange-50/30">
                    <td className="px-3 py-2.5 font-medium text-slate-800">{r.customer}</td>
                    <td className="px-3 py-2.5 text-slate-600">{r.program}</td>
                    <td className="px-3 py-2.5 text-slate-600">{r.lot}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">{r.paid}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">{r.payment_pct}%</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-700">{r.construction_pct}%</td>
                    <td className={`px-3 py-2.5 text-right font-bold tabular-nums ${r.idcp >= 20 ? 'text-rose-600' : r.idcp <= -8 ? 'text-sky-600' : 'text-slate-700'}`}>
                      {r.idcp > 0 ? '+' : ''}{r.idcp}%
                    </td>
                    <td className="px-3 py-2.5 text-slate-600">{r.sales_agent}</td>
                    <td className="px-3 py-2.5 text-slate-500">{formatDate(r.sale_date)}</td>
                    <td className="px-3 py-2.5"><span className={`rounded-full px-2 py-0.5 text-xs font-medium ${s.bg} ${s.text}`}>{s.label}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {payload && (payload.next || payload.previous) && (
        <Pagination payload={payload} onPage={(p) => setParam('page', String(p))} />
      )}
    </div>
  )
}

function Pagination({ payload, onPage }) {
  const page = Number(new URLSearchParams(window.location.hash.split('?')[1] || '').get('page')) || 1
  return (
    <div className="mt-4 flex items-center justify-center gap-3">
      <button type="button" disabled={!payload.previous} onClick={() => onPage(page - 1)}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40">← Précédent</button>
      <span className="text-sm text-slate-600">{payload.count} dossiers</span>
      <button type="button" disabled={!payload.next} onClick={() => onPage(page + 1)}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40">Suivant →</button>
    </div>
  )
}
