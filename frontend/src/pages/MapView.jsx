import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getMapAssets } from '../api/map'
import useReferenceData from '../hooks/useReferenceData'
import MapCanvas from '../components/map/MapCanvas'
import MapToolbar from '../components/map/MapToolbar'
import MapLegend from '../components/map/MapLegend'
import FeatureDetailPanel from '../components/map/FeatureDetailPanel'

const FILTER_KEYS = ['project', 'program', 'status', 'tag', 'search']
const DEFAULT_STATUS_FILTERS = ['Tous', 'Disponibles', 'Réservés', 'Vendus', 'En construction']
const ORTHO_MODES = new Set(['orthophoto', 'mixte'])

export default function MapView() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { refData } = useReferenceData()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [mode, setMode] = useState('parcelles')

  const [orthoVersionId, setOrthoVersionId] = useState('')
  const [orthoOpacity, setOrthoOpacity] = useState(0.9)

  const filters = useMemo(() => {
    const r = {}
    FILTER_KEYS.forEach((k) => { r[k] = searchParams.get(k) || '' })
    return r
  }, [searchParams])

  const fitToken = useMemo(() => FILTER_KEYS.map((k) => filters[k]).join('|'), [filters])

  // Chargement (zoom 15 : géométrie incluse, images/timeline exclues car
  // ≥16 = une requête SQL par parcelle ; pas de bbox — cf. frontend/README).
  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true)
    const controller = new AbortController()
    getMapAssets({ ...filters, zoom: 15, limit: 11200 }, { signal: controller.signal })
      .then((payload) => { setData(payload); setError(null) })
      .catch((err) => { if (err.name !== 'AbortError') setError(err) })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [filters])

  useEffect(() => load(), [load])

  function setFilters(next) {
    const params = new URLSearchParams()
    FILTER_KEYS.forEach((k) => { if (next[k]) params.set(k, next[k]) })
    setSearchParams(params)
    setSelected(null)
    setOrthoVersionId('')
  }

  // Programme dont on affiche l'orthophoto : celui filtré s'il en a une,
  // sinon le premier programme disposant d'une orthophoto prête.
  const orthoEntry = useMemo(() => {
    const map = data?.orthophotos_by_program || {}
    const ready = (e) => e && (e.current?.is_ready || (e.versions || []).some((o) => o.is_ready))
    if (filters.program && ready(map[filters.program])) return map[filters.program]
    return Object.values(map).find(ready) || null
  }, [data, filters.program])

  const orthoVersions = useMemo(
    () => (orthoEntry?.versions || []).filter((o) => o.is_ready),
    [orthoEntry],
  )

  const orthoLayer = useMemo(() => {
    if (!ORTHO_MODES.has(mode) || !orthoEntry) return null
    const chosen = orthoVersionId
      ? orthoVersions.find((o) => String(o.id) === String(orthoVersionId))
      : orthoEntry.current
    return chosen && chosen.is_ready ? chosen : null
  }, [mode, orthoEntry, orthoVersionId, orthoVersions])

  const statusFilters = data?.filters || DEFAULT_STATUS_FILTERS

  return (
    <div className="relative -mx-4 -my-6 h-[calc(100vh-57px)] overflow-hidden sm:-mx-6">
      <MapCanvas
        assets={data?.assets || []}
        selectedUid={selected?.uid || null}
        onSelect={setSelected}
        orthoLayer={orthoLayer}
        orthoOpacity={orthoOpacity}
        fitToken={fitToken}
        mode={mode}
      />

      <MapToolbar
        refData={refData}
        value={filters}
        onChange={setFilters}
        mode={mode}
        onMode={setMode}
        counts={data?.counts}
        truncated={data?.truncated}
        statusFilters={statusFilters}
      />

      {/* Légende + synthèse (bas-gauche) */}
      <div className="absolute bottom-3 left-3 z-[600]">
        <MapLegend summaries={data?.summaries || []} variant={mode === 'noms' ? 'priority' : 'status'} />
      </div>

      {/* Contrôle orthophoto (bas-centre) — visible seulement si une couche
          est active dans les modes Orthophoto / Mixte. */}
      {orthoLayer && (
        <div className="absolute bottom-3 left-1/2 z-[600] -translate-x-1/2 rounded-2xl bg-white/95 px-4 py-2.5 shadow-xl backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--kaydan)' }}>
              {orthoEntry?.program_name || 'Orthophoto'}
            </span>
            {orthoVersions.length > 0 && (
              <select
                value={orthoVersionId}
                onChange={(e) => setOrthoVersionId(e.target.value)}
                className="rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-700 focus:border-orange-400 focus:ring-orange-400"
              >
                <option value="">Version courante</option>
                {orthoVersions.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.period_label || `${o.reference_month || '?'}/${o.reference_year || '?'}`}
                    {o.is_current ? ' (courante)' : ''}
                  </option>
                ))}
              </select>
            )}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-slate-400">Opacité</span>
              <input
                type="range" min={0.2} max={1} step={0.05}
                value={orthoOpacity}
                onChange={(e) => setOrthoOpacity(Number(e.target.value))}
              />
            </div>
          </div>
        </div>
      )}

      {/* État */}
      {loading && (
        <div className="absolute right-3 top-24 z-[600] rounded-full bg-white/95 px-3 py-1.5 text-sm text-slate-600 shadow-lg backdrop-blur">
          Chargement…
        </div>
      )}
      {error && (
        <div className="absolute right-3 top-24 z-[600] max-w-xs rounded-xl border border-rose-200 bg-rose-50 px-3 py-1.5 text-sm text-rose-700 shadow-lg">
          {error.message}
        </div>
      )}

      {/* Panneau détail (droite, flottant) */}
      {selected && (
        <div className="absolute bottom-3 right-3 top-[8.5rem] z-[600] w-[22rem] max-w-[calc(100vw-1.5rem)] overflow-hidden rounded-2xl shadow-2xl">
          <FeatureDetailPanel feature={selected} onClose={() => setSelected(null)} />
        </div>
      )}
    </div>
  )
}
