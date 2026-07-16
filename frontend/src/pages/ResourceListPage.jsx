import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { listResource } from '../api/resources'
import { getResourceConfig } from '../config/resources'
import useOptions from '../hooks/useOptions'
import { badgeClass } from '../lib/badges'
import { formatDate } from '../lib/format'

export default function ResourceListPage() {
  const { resource } = useParams()
  const config = getResourceConfig(resource)
  const navigate = useNavigate()
  const options = useOptions()
  const [searchParams, setSearchParams] = useSearchParams()
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchInput, setSearchInput] = useState(searchParams.get('search') || '')
  const searchTimer = useRef(null)

  const filterKeys = useMemo(() => (config?.filters || []).map((f) => f.key), [config])

  const params = useMemo(() => {
    const p = {}
    for (const [k, v] of searchParams.entries()) p[k] = v
    return p
  }, [searchParams])

  const load = useCallback(() => {
    if (!config) return undefined
    setLoading(true)
    const controller = new AbortController()
    listResource(config.endpoint, params, { signal: controller.signal })
      .then((data) => { setPayload(data); setError(null) })
      .catch((err) => { if (err.name !== 'AbortError') setError(err) })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [config, params])

  useEffect(() => { setSearchInput(searchParams.get('search') || '') }, [resource])
  useEffect(() => load(), [load])

  if (!config) return <div className="py-20 text-center text-slate-500">Ressource inconnue.</div>

  function setParam(key, value) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value); else next.delete(key)
    if (key !== 'page') next.delete('page')
    setSearchParams(next)
  }
  function onSearch(v) {
    setSearchInput(v)
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => setParam('search', v.trim()), 400)
  }
  function toggleSort(key) {
    const current = searchParams.get('ordering')
    setParam('ordering', current === key ? `-${key}` : (current === `-${key}` ? key : key))
  }

  const canAdd = config.writable && options?.permissions?.[config.permKey]?.add
  const opt = (k) => (options?.[k] || [])

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{config.title}</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {payload ? `${payload.count} ${payload.count > 1 ? 'éléments' : 'élément'}` : '…'}
          </p>
        </div>
        {canAdd && (
          <Link to={`/r/${resource}/new`}
            className="rounded-lg px-4 py-2 text-sm font-semibold text-white shadow-sm"
            style={{ background: 'var(--kaydan)' }}>
            + Nouveau {config.singular.toLowerCase()}
          </Link>
        )}
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <input
          type="search" value={searchInput} onChange={(e) => onSearch(e.target.value)}
          placeholder="Rechercher…"
          className="w-56 rounded-lg border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-orange-400 focus:ring-orange-400"
        />
        {(config.filters || []).map((f) => (
          <select key={f.key} value={searchParams.get(f.key) || ''} onChange={(e) => setParam(f.key, e.target.value)}
            className="rounded-lg border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-700 shadow-sm focus:border-orange-400 focus:ring-orange-400">
            <option value="">{f.label}</option>
            {opt(f.optionsKey).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ))}
        {(searchParams.get('search') || filterKeys.some((k) => searchParams.get(k))) && (
          <button type="button" onClick={() => { setSearchInput(''); setSearchParams({}) }}
            className="text-sm text-orange-600 hover:underline">Réinitialiser</button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error.message}</div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                {config.columns.map((c) => (
                  <th key={c.key}
                    onClick={() => toggleSort(c.key)}
                    className={`cursor-pointer select-none px-4 py-2.5 font-semibold text-slate-600 ${c.align === 'right' ? 'text-right' : 'text-left'}`}>
                    {c.label}
                    {searchParams.get('ordering') === c.key && ' ▲'}
                    {searchParams.get('ordering') === `-${c.key}` && ' ▼'}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && !payload ? (
                <tr><td colSpan={config.columns.length} className="px-4 py-16 text-center text-slate-400">Chargement…</td></tr>
              ) : payload?.results?.length === 0 ? (
                <tr><td colSpan={config.columns.length} className="px-4 py-16 text-center text-slate-500">Aucun résultat.</td></tr>
              ) : payload?.results?.map((row) => (
                <tr key={row.id} onClick={() => navigate(`/r/${resource}/${row.id}`)}
                  className="cursor-pointer hover:bg-orange-50/40">
                  {config.columns.map((c) => (
                    <td key={c.key} className={`px-4 py-2.5 text-slate-700 ${c.align === 'right' ? 'text-right tabular-nums' : ''}`}>
                      {c.badge ? (
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badgeClass(row[c.key])}`}>{row[c.key] || '—'}</span>
                      ) : c.type === 'date' ? formatDate(row[c.key]) : (row[c.key] ?? '—')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {payload && payload.count > (payload.results?.length || 0) && (
        <Pagination payload={payload} onPage={(p) => setParam('page', String(p))} />
      )}
    </div>
  )
}

function Pagination({ payload, onPage }) {
  const pageSize = 25
  const page = Number(new URLSearchParams(window.location.hash.split('?')[1] || '').get('page')) || 1
  const pages = Math.ceil(payload.count / pageSize)
  return (
    <div className="mt-4 flex items-center justify-center gap-3">
      <button type="button" disabled={!payload.previous} onClick={() => onPage(page - 1)}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40">← Précédent</button>
      <span className="text-sm text-slate-600">Page {page} / {pages}</span>
      <button type="button" disabled={!payload.next} onClick={() => onPage(page + 1)}
        className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40">Suivant →</button>
    </div>
  )
}
