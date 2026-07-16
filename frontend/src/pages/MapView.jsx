import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getMapAssets } from '../api/map'
import useReferenceData from '../hooks/useReferenceData'
import MapCanvas from '../components/map/MapCanvas'
import MapFilters from '../components/map/MapFilters'
import MapLegend from '../components/map/MapLegend'
import FeatureDetailPanel from '../components/map/FeatureDetailPanel'

const FILTER_KEYS = ['project', 'program', 'status', 'tag', 'search']
const DEFAULT_STATUS_FILTERS = ['Tous', 'Disponibles', 'Réservés', 'Vendus', 'En construction']

export default function MapView() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { refData } = useReferenceData()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  // Couche orthophoto : programme choisi + version (orthophoto id) + opacité.
  const [orthoProgram, setOrthoProgram] = useState('')
  const [orthoVersionId, setOrthoVersionId] = useState('')
  const [orthoOpacity, setOrthoOpacity] = useState(0.85)

  const filters = useMemo(() => {
    const r = {}
    FILTER_KEYS.forEach((k) => { r[k] = searchParams.get(k) || '' })
    return r
  }, [searchParams])

  // Jeton de recadrage : change quand les filtres changent (pas au pan/zoom).
  const fitToken = useMemo(() => FILTER_KEYS.map((k) => filters[k]).join('|'), [filters])

  // Le jeu de données tient sans découpage géographique : on ne filtre PAS
  // par bbox du viewport (les parcelles d'un même programme peuvent être à
  // plusieurs centaines de km — Abidjan vs Yaokro). On charge tout ce qui
  // correspond aux filtres au zoom 15 : la géométrie est incluse (seuil ≥14)
  // SANS les images/timeline (seuil ≥16, coûteux : une requête par parcelle).
  // Les photos/l'historique restent accessibles via « Ouvrir la fiche ».
  const load = useCallback((silent = false) => {
    if (!silent) setLoading(true)
    const controller = new AbortController()
    getMapAssets(
      { ...filters, zoom: 15, limit: 11200 },
      { signal: controller.signal },
    )
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
  }

  // NB : l'API expose {program_id, program_name, current, versions}.
  // Couche orthophoto active = version choisie, sinon courante du programme.
  const orthoLayer = useMemo(() => {
    if (!orthoProgram || !data?.orthophotos_by_program) return null
    const entry = data.orthophotos_by_program[orthoProgram]
    if (!entry) return null
    const versions = entry.versions || []
    const chosen = orthoVersionId
      ? versions.find((o) => String(o.id) === String(orthoVersionId))
      : entry.current
    return chosen && chosen.is_ready ? chosen : null
  }, [orthoProgram, orthoVersionId, data])

  const orthoVersions = useMemo(() => {
    if (!orthoProgram || !data?.orthophotos_by_program) return []
    return (data.orthophotos_by_program[orthoProgram]?.versions || []).filter((o) => o.is_ready)
  }, [orthoProgram, data])

  // Programmes ayant au moins une orthophoto prête (pour le sélecteur de couche).
  const programsWithOrtho = useMemo(() => {
    const map = data?.orthophotos_by_program || {}
    return Object.values(map)
      .filter((e) => e.current?.is_ready || (e.versions || []).some((o) => o.is_ready))
      .map((e) => ({ id: e.program_id, name: e.program_name }))
  }, [data])

  const statusFilters = data?.filters || DEFAULT_STATUS_FILTERS
  const sel = 'rounded-lg border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-700 shadow-sm focus:border-sky-500 focus:ring-sky-500'

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-3">
      {/* Barre de filtres */}
      <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
        <MapFilters
          refData={refData}
          statusFilters={statusFilters}
          tagFilters={data?.tag_filters || []}
          value={filters}
          onChange={setFilters}
          counts={data?.counts}
          truncated={data?.truncated}
        />
      </div>

      {/* Carte + panneau */}
      <div className="relative flex flex-1 gap-3 overflow-hidden">
        <div className="relative flex-1 overflow-hidden rounded-xl border border-slate-200 bg-slate-100 shadow-sm">
          <MapCanvas
            assets={data?.assets || []}
            selectedUid={selected?.uid || null}
            onSelect={setSelected}
            orthoLayer={orthoLayer}
            orthoOpacity={orthoOpacity}
            fitToken={fitToken}
          />

          {/* Contrôle couche orthophoto (haut-gauche) */}
          <div className="absolute left-3 top-3 z-[500] w-64 rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Couche orthophoto
            </label>
            <select
              value={orthoProgram}
              onChange={(e) => { setOrthoProgram(e.target.value); setOrthoVersionId('') }}
              className={`${sel} w-full`}
            >
              <option value="">Aucune</option>
              {programsWithOrtho.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
            {orthoProgram && orthoVersions.length > 0 && (
              <>
                <select
                  value={orthoVersionId}
                  onChange={(e) => setOrthoVersionId(e.target.value)}
                  className={`${sel} mt-2 w-full`}
                >
                  <option value="">Version courante</option>
                  {orthoVersions.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.period_label || `${o.reference_month || '?'}/${o.reference_year || '?'}`}
                      {o.is_current ? ' (courante)' : ''}
                    </option>
                  ))}
                </select>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-xs text-slate-500">Opacité</span>
                  <input
                    type="range" min={0.2} max={1} step={0.05}
                    value={orthoOpacity}
                    onChange={(e) => setOrthoOpacity(Number(e.target.value))}
                    className="flex-1"
                  />
                </div>
              </>
            )}
          </div>

          {/* Légende + synthèse (bas-gauche) */}
          <div className="absolute bottom-3 left-3 z-[500] max-w-xs">
            <MapLegend summaries={data?.summaries || []} />
          </div>

          {/* Indicateurs d'état */}
          {loading && (
            <div className="absolute right-3 top-3 z-[500] rounded-lg bg-white/95 px-3 py-1.5 text-sm text-slate-600 shadow">
              Chargement…
            </div>
          )}
          {error && (
            <div className="absolute right-3 top-3 z-[500] max-w-xs rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-sm text-rose-700 shadow">
              {error.message}
            </div>
          )}
        </div>

        {/* Panneau latéral de détail */}
        {selected && (
          <div className="w-80 shrink-0 overflow-hidden rounded-xl border border-slate-200 shadow-sm">
            <FeatureDetailPanel feature={selected} onClose={() => setSelected(null)} />
          </div>
        )}
      </div>
    </div>
  )
}
