import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { getMapAssets } from '../api/map'
import { getAlertMap } from '../api/analytics'
import useReferenceData from '../hooks/useReferenceData'
import MapCanvas from '../components/map/MapCanvas'
import MapToolbar from '../components/map/MapToolbar'
import MapLegend from '../components/map/MapLegend'
import ControlRail from '../components/map/ControlRail'
import ViewSelector from '../components/map/ViewSelector'
import FeatureDetailPanel from '../components/map/FeatureDetailPanel'
import { useToast } from '../components/Toasts'

const FILTER_KEYS = ['project', 'program', 'status', 'tag', 'search']
const DEFAULT_STATUS_FILTERS = ['Tous', 'Disponibles', 'Réservés', 'Vendus', 'En construction']
const STATUS_CMDS = { disponible: 'Disponibles', réservé: 'Réservés', reserve: 'Réservés', vendu: 'Vendus', construction: 'En construction' }

export default function MapView() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { refData } = useReferenceData()
  const toast = useToast()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  const [basemap, setBasemap] = useState('standard')
  const [layerStyle, setLayerStyle] = useState('polygones')
  const [alertMap, setAlertMap] = useState(null)
  const [showAlerts, setShowAlerts] = useState(true)
  const [orthoOn, setOrthoOn] = useState(false)
  const [orthoProgramId, setOrthoProgramId] = useState('')
  const [orthoOpacity] = useState(0.9)

  const [api, setApi] = useState(null)
  const [measure, setMeasure] = useState({ active: false })
  const [minimapOn, setMinimapOn] = useState(false)
  const [railCollapsed, setRailCollapsed] = useState(false)
  const [cursorOn, setCursorOn] = useState(false)
  const [cursor, setCursor] = useState(null)

  const filters = useMemo(() => {
    const r = {}
    FILTER_KEYS.forEach((k) => { r[k] = searchParams.get(k) || '' })
    return r
  }, [searchParams])

  const fitToken = useMemo(() => FILTER_KEYS.map((k) => filters[k]).join('|'), [filters])

  const load = useCallback(() => {
    setLoading(true)
    const controller = new AbortController()
    getMapAssets({ ...filters, zoom: 15, limit: 11200 }, { signal: controller.signal })
      .then((payload) => { setData(payload); setError(null) })
      .catch((err) => { if (err.name !== 'AbortError') setError(err) })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [filters])

  useEffect(() => load(), [load])
  useEffect(() => { if (api) api.toggleMinimap(minimapOn) }, [api, minimapOn])

  // Sévérité d'alerte active par parcelle (chargée une fois pour le surlignage).
  useEffect(() => {
    const controller = new AbortController()
    getAlertMap({ signal: controller.signal }).then(setAlertMap).catch(() => {})
    return () => controller.abort()
  }, [])
  const alertLevels = useMemo(() => alertMap?.by_parcel || {}, [alertMap])
  const selectedAlert = useMemo(
    () => (selected?.parcel_id != null ? alertLevels[String(selected.parcel_id)] : null),
    [selected, alertLevels],
  )

  function setFilters(next) {
    const params = new URLSearchParams()
    FILTER_KEYS.forEach((k) => { if (next[k]) params.set(k, next[k]) })
    setSearchParams(params)
    setSelected(null)
  }

  // Programmes du jeu courant disposant d'une orthophoto prête.
  const orthoPrograms = useMemo(() => {
    const map = data?.orthophotos_by_program || {}
    return Object.values(map)
      .filter((e) => e.current?.is_ready)
      .map((e) => ({ id: String(e.program_id), name: e.program_name }))
  }, [data])

  // Programme dont on affiche l'orthophoto : choix explicite, sinon
  // programme filtré, sinon 1er équipé. Réinitialisé au changement de filtre.
  const effectiveOrthoProgram = useMemo(() => {
    if (orthoProgramId && orthoPrograms.some((p) => p.id === orthoProgramId)) return orthoProgramId
    if (filters.program && orthoPrograms.some((p) => p.id === String(filters.program))) return String(filters.program)
    return orthoPrograms[0]?.id || ''
  }, [orthoProgramId, orthoPrograms, filters.program])

  const orthoLayer = useMemo(() => {
    if (!orthoOn || !effectiveOrthoProgram) return null
    const entry = data?.orthophotos_by_program?.[effectiveOrthoProgram]
    return entry?.current?.is_ready ? entry.current : null
  }, [orthoOn, effectiveOrthoProgram, data])

  // Recentrer la carte sur l'orthophoto affichée (sinon elle peut être hors
  // champ quand un projet multi-programmes est sélectionné). Le centroïde
  // n'est pas toujours renseigné → repli sur l'emprise (bounds).
  useEffect(() => {
    if (!orthoOn || !orthoLayer || !api) return
    if (Array.isArray(orthoLayer.centroid)) api.flyTo(orthoLayer.centroid, 16)
    else if (orthoLayer.bounds) api.fitGeoJson(orthoLayer.bounds)
  }, [orthoOn, orthoLayer, api])

  // Réinitialise le choix manuel quand les filtres changent.
  useEffect(() => { setOrthoProgramId('') }, [filters.project, filters.program])

  // Suggestions de recherche : biens chargés + programmes + projets + commandes statut.
  const buildSuggestions = useCallback((raw) => {
    const term = raw.toLowerCase()
    const out = []
    // Commande de statut
    Object.entries(STATUS_CMDS).forEach(([kw, val]) => {
      if (term.includes(kw)) out.push({
        badge: '⚑', color: '#e2571e', label: `Filtrer : ${val}`, sub: 'Commande carte',
        action: () => setFilters({ ...filters, status: val }),
      })
    })
    // Programmes / projets
    ;(refData?.programs || []).filter((p) => p.name.toLowerCase().includes(term)).slice(0, 3).forEach((p) => out.push({
      badge: '▣', color: '#0ea5e9', label: p.name, sub: 'Programme',
      action: () => setFilters({ ...filters, program: String(p.id), project: '' }),
    }))
    ;(refData?.projects || []).filter((p) => p.name.toLowerCase().includes(term)).slice(0, 2).forEach((p) => out.push({
      badge: '◆', color: '#8b5cf6', label: p.name, sub: 'Projet',
      action: () => setFilters({ ...filters, project: String(p.id), program: '' }),
    }))
    // Biens chargés
    ;(data?.assets || []).filter((a) => (a.name || '').toLowerCase().includes(term)).slice(0, 6).forEach((a) => out.push({
      badge: '⌂', color: a.color, label: a.name, sub: `${a.program} · ${a.status}`,
      action: () => { setSelected(a); if (a.center && api) { /* centrage géré par sélection */ } },
    }))
    return out.slice(0, 12)
  }, [refData, data, filters, api])

  const statusFilters = data?.filters || DEFAULT_STATUS_FILTERS
  const canOrtho = orthoPrograms.length > 0

  return (
    <div data-map-root className="relative -mx-4 -my-6 h-[calc(100vh-53px)] overflow-hidden bg-slate-200 sm:-mx-6">
      <MapCanvas
        assets={data?.assets || []}
        selectedUid={selected?.uid || null}
        onSelect={setSelected}
        fitToken={fitToken}
        basemap={basemap}
        layerStyle={layerStyle}
        orthoLayer={orthoLayer}
        orthoOpacity={orthoOpacity}
        alertLevels={alertLevels}
        showAlerts={showAlerts}
        onReady={setApi}
        onMeasure={setMeasure}
        onCursor={setCursor}
      />

      <MapToolbar
        refData={refData} value={filters} onChange={setFilters}
        statusFilters={statusFilters} counts={data?.counts} truncated={data?.truncated}
        buildSuggestions={buildSuggestions}
      />

      <ControlRail
        api={api} measure={measure} minimapOn={minimapOn} onMinimap={setMinimapOn}
        collapsed={railCollapsed} onToggle={setRailCollapsed}
        hasSelection={!!selected}
        onRecenterSelection={() => { if (selected?.center && api) api.flyTo(selected.center, 18) }}
        cursorOn={cursorOn}
        onCursorToggle={() => { const v = !cursorOn; setCursorOn(v); api?.setCursor(v); if (!v) setCursor(null) }}
        onShare={async () => {
          try { await navigator.clipboard.writeText(window.location.href); toast('Lien de la vue copié.', 'success') }
          catch { toast('Copie impossible — copiez l’URL manuellement.', 'error') }
        }}
      />

      <ViewSelector
        basemap={basemap} onBasemap={setBasemap}
        layerStyle={layerStyle} onLayerStyle={setLayerStyle}
        alertsActive={showAlerts} onAlertsToggle={() => setShowAlerts((a) => !a)}
        orthoActive={orthoOn} onOrthoToggle={() => setOrthoOn((o) => !o)} canOrtho={canOrtho}
        orthoPrograms={orthoPrograms} orthoProgramId={effectiveOrthoProgram} onOrthoProgram={setOrthoProgramId}
      />

      {/* Légende (bas-gauche) — masquée quand le panneau détail est ouvert
          pour éviter tout chevauchement. */}
      {!selected && (
        <div className="absolute bottom-3 left-3 z-[640]">
          <MapLegend summaries={data?.summaries || []} variant={layerStyle === 'noms' ? 'priority' : 'status'} />
        </div>
      )}

      {/* Relevé de coordonnées du curseur */}
      <AnimatePresence>
        {cursorOn && cursor && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="glass absolute bottom-3 right-3 z-[650] rounded-full px-3 py-1.5 font-mono text-xs text-slate-700">
            {cursor.lat.toFixed(5)}, {cursor.lng.toFixed(5)}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Bandeau de mesure actif */}
      <AnimatePresence>
        {measure.active && (
          <motion.div
            initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
            className="glass absolute left-1/2 top-20 z-[650] -translate-x-1/2 rounded-full px-4 py-2 text-sm font-medium text-slate-700">
            📏 {measure.text || 'Mesure en cours'} <span className="ml-2 text-slate-400">— cliquez pour ajouter des points</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* États */}
      <AnimatePresence>
        {loading && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="glass absolute left-1/2 top-3 z-[650] -translate-x-1/2 rounded-full px-4 py-1.5 text-sm text-slate-600">
            Chargement de la carte…
          </motion.div>
        )}
      </AnimatePresence>
      {error && (
        <div className="absolute left-1/2 top-3 z-[650] -translate-x-1/2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-1.5 text-sm text-rose-700 shadow">
          {error.message}
        </div>
      )}

      {/* Panneau détail premium (droite) */}
      <AnimatePresence>
        {selected && (
          <motion.div
            initial={{ opacity: 0, y: 40, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, x: 0, scale: 1 }}
            exit={{ opacity: 0, y: 40, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
            className="glass absolute z-[680] overflow-hidden rounded-2xl
                       inset-x-2 bottom-2 h-[58vh]
                       sm:inset-x-auto sm:bottom-3 sm:right-3 sm:top-[4.75rem] sm:h-auto sm:w-[22rem]"
          >
            <FeatureDetailPanel feature={selected} alert={selectedAlert} onClose={() => setSelected(null)} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
