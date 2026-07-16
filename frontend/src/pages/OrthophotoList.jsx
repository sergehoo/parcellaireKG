import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { listOrthophotos } from '../api/orthophotos'
import useReferenceData from '../hooks/useReferenceData'
import StatusBadge from '../components/StatusBadge'
import ProgressBar from '../components/ProgressBar'
import { formatDateTime, monthName, periodLabel } from '../lib/format'

const FILTER_KEYS = ['project', 'program', 'year', 'month', 'status', 'q', 'page']

export default function OrthophotoList() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { refData } = useReferenceData()
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchInput, setSearchInput] = useState(searchParams.get('q') || '')
  const searchTimer = useRef(null)

  const filters = useMemo(() => {
    const result = {}
    FILTER_KEYS.forEach((key) => {
      const value = searchParams.get(key)
      if (value) result[key] = value
    })
    return result
  }, [searchParams])

  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true)
    const controller = new AbortController()
    listOrthophotos(filters, { signal: controller.signal })
      .then((data) => { setPayload(data); setError(null) })
      .catch((err) => { if (err.name !== 'AbortError') setError(err) })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [filters])

  useEffect(() => load(), [load])

  // Rafraîchit silencieusement toutes les 5 s tant qu'un traitement tourne.
  const hasInProgress = payload?.results?.some(
    (o) => o.status === 'PENDING' || o.status === 'PROCESSING',
  )
  useEffect(() => {
    if (!hasInProgress) return undefined
    const interval = setInterval(() => load(true), 5000)
    return () => clearInterval(interval)
  }, [hasInProgress, load])

  function setFilter(key, value) {
    const next = new URLSearchParams(searchParams)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'page') next.delete('page')
    // Changer de projet invalide le programme sélectionné.
    if (key === 'project') next.delete('program')
    setSearchParams(next)
  }

  function onSearchChange(value) {
    setSearchInput(value)
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => setFilter('q', value.trim()), 400)
  }

  const programs = useMemo(() => {
    if (!refData) return []
    const projectId = searchParams.get('project')
    return projectId
      ? refData.programs.filter((p) => String(p.project_id) === projectId)
      : refData.programs
  }, [refData, searchParams])

  const selectClass = 'rounded-lg border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-sky-500 focus:ring-sky-500'

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Orthophotos</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {payload ? `${payload.count} orthophoto${payload.count > 1 ? 's' : ''}` : '…'}
          </p>
        </div>
        {refData?.user?.can_add && (
          <Link
            to="/upload"
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-sky-700"
          >
            + Nouvelle orthophoto
          </Link>
        )}
      </div>

      {/* Filtres */}
      <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <input
          type="search"
          value={searchInput}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Rechercher (nom, programme, projet…)"
          className="w-64 rounded-lg border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-sky-500 focus:ring-sky-500"
        />
        <select value={searchParams.get('project') || ''} onChange={(e) => setFilter('project', e.target.value)} className={selectClass}>
          <option value="">Tous les projets</option>
          {refData?.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={searchParams.get('program') || ''} onChange={(e) => setFilter('program', e.target.value)} className={selectClass}>
          <option value="">Tous les programmes</option>
          {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={searchParams.get('year') || ''} onChange={(e) => setFilter('year', e.target.value)} className={selectClass}>
          <option value="">Année</option>
          {refData?.years.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
        <select value={searchParams.get('month') || ''} onChange={(e) => setFilter('month', e.target.value)} className={selectClass}>
          <option value="">Mois</option>
          {refData?.months.map((m) => <option key={m} value={m}>{monthName(m)}</option>)}
        </select>
        <select value={searchParams.get('status') || ''} onChange={(e) => setFilter('status', e.target.value)} className={selectClass}>
          <option value="">Tous les statuts</option>
          {refData?.statuses.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        {FILTER_KEYS.some((k) => searchParams.get(k)) && (
          <button
            type="button"
            onClick={() => { setSearchInput(''); setSearchParams({}) }}
            className="text-sm text-sky-600 hover:underline"
          >
            Réinitialiser
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error.message}
        </div>
      )}

      {loading && !payload ? (
        <div className="py-20 text-center text-slate-500">Chargement…</div>
      ) : payload?.results?.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white py-20 text-center">
          <p className="text-slate-600">Aucune orthophoto ne correspond aux filtres.</p>
          {refData?.user?.can_add && (
            <Link to="/upload" className="mt-2 inline-block text-sm font-medium text-sky-600 hover:underline">
              Importer une orthophoto
            </Link>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {payload?.results?.map((ortho) => (
            <Link
              key={ortho.id}
              to={`/orthophotos/${ortho.id}`}
              className="group rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-sky-300 hover:shadow"
            >
              <div className="mb-2 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="truncate font-semibold text-slate-900 group-hover:text-sky-700">
                    {ortho.name || periodLabel(ortho)}
                  </h2>
                  <p className="truncate text-sm text-slate-500">
                    {ortho.program.project ? `${ortho.program.project.name} · ` : ''}
                    {ortho.program.name}
                  </p>
                </div>
                <StatusBadge status={ortho.status} label={ortho.status_display} />
              </div>
              <p className="mb-3 text-sm text-slate-600">
                Période : <span className="font-medium">{periodLabel(ortho)}</span>
                {ortho.is_current && (
                  <span className="ml-2 rounded bg-sky-50 px-1.5 py-0.5 text-xs font-medium text-sky-700 ring-1 ring-sky-200">
                    Courante
                  </span>
                )}
              </p>
              {(ortho.status === 'PROCESSING' || ortho.status === 'PENDING') && (
                <ProgressBar
                  percent={ortho.progress_percent}
                  status={ortho.status}
                  label={ortho.current_step}
                />
              )}
              {ortho.status === 'FAILED' && ortho.error_message && (
                <p className="truncate text-xs text-rose-600">{ortho.error_message}</p>
              )}
              <p className="mt-3 text-xs text-slate-400">
                Importée le {formatDateTime(ortho.created_at)}
                {ortho.created_by ? ` par ${ortho.created_by}` : ''}
              </p>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      {payload && payload.pages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-3">
          <button
            type="button"
            disabled={payload.page <= 1}
            onClick={() => setFilter('page', String(payload.page - 1))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40"
          >
            ← Précédent
          </button>
          <span className="text-sm text-slate-600">
            Page {payload.page} / {payload.pages}
          </span>
          <button
            type="button"
            disabled={payload.page >= payload.pages}
            onClick={() => setFilter('page', String(payload.page + 1))}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm disabled:opacity-40"
          >
            Suivant →
          </button>
        </div>
      )}
    </div>
  )
}
