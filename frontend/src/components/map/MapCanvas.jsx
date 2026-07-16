import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet.markercluster'
import 'leaflet-minimap'
import * as turf from '@turf/turf'

/**
 * Canvas Leaflet premium. Piloté par props + une API impérative exposée
 * via `onReady` (zoom, recentrage, localisation, plein écran, mesures,
 * mini-carte, impression) — consommée par le rail de contrôle React.
 *
 * Fonds de carte (`basemap`) : standard / clair / sombre / satellite /
 * relief. Style de calque parcelles (`layerStyle`) : polygones / noms /
 * reperes (clustering) / none. Overlay orthophoto optionnel.
 */

export const BASEMAPS = {
  standard: {
    label: 'Standard',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    options: { maxZoom: 22, maxNativeZoom: 19, attribution: '© OpenStreetMap' },
  },
  clair: {
    label: 'Clair',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    options: { maxZoom: 22, maxNativeZoom: 20, attribution: '© OpenStreetMap © CARTO' },
  },
  sombre: {
    label: 'Sombre',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    options: { maxZoom: 22, maxNativeZoom: 20, attribution: '© OpenStreetMap © CARTO' },
  },
  satellite: {
    label: 'Satellite',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    options: { maxZoom: 22, maxNativeZoom: 19, attribution: '© Esri, Maxar, Earthstar Geographics' },
  },
  relief: {
    label: 'Relief',
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    options: { maxZoom: 22, maxNativeZoom: 17, subdomains: 'abc', attribution: '© OpenTopoMap (CC-BY-SA)' },
  },
}

function priorityBg(feat) {
  const p = feat.priority_stats?.priority
  if (p === 'HIGH') return '#7f1d1d'
  if (p === 'MEDIUM') return '#78350f'
  return '#1e293b'
}

function statFragment(feat) {
  const cs = feat.construction_stats || {}
  const fs = feat.financial_stats || {}
  const t = cs.taux_avancement && cs.taux_avancement !== 'Masqué' ? `T:${cs.taux_avancement}` : ''
  const p = fs.taux_paiement && fs.taux_paiement !== 'Masqué' ? `P:${fs.taux_paiement}` : ''
  let v = ''
  const ev = cs.evolution_mensuelle
  if (typeof ev === 'number' && ev !== 0) {
    v = `<span class="${ev > 0 ? 'v-pos' : 'v-neg'}">V:${ev > 0 ? '+' : ''}${Math.round(ev)}%</span>`
  }
  return [t, v, p].filter(Boolean).join(' · ')
}

function chipHtml(feat) {
  const stats = statFragment(feat)
  return `<div class="lot-name">${feat.name || '—'}</div>` + (stats ? `<div class="lot-stats">${stats}</div>` : '')
}

function markerIcon(feat) {
  const color = feat.color || '#e2571e'
  return L.divIcon({
    className: '',
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    html: `<span style="display:block;width:14px;height:14px;border-radius:9999px;background:${color};border:2.5px solid #fff;box-shadow:0 2px 6px rgba(2,6,23,.4)"></span>`,
  })
}

export default function MapCanvas({
  assets = [], selectedUid = null, onSelect, fitToken = '',
  basemap = 'standard', layerStyle = 'polygones',
  orthoLayer = null, orthoOpacity = 1,
  onReady, onMeasure,
}) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const baseRef = useRef(null)
  const featureLayerRef = useRef(null)
  const orthoRef = useRef(null)
  const layerByUidRef = useRef(new Map())
  const lastFitRef = useRef(null)
  const locateRef = useRef(null)
  const measureRef = useRef(null) // {type, points, layer, tip}
  const miniRef = useRef(null)
  const onSelectRef = useRef(onSelect)
  const onMeasureRef = useRef(onMeasure)
  onSelectRef.current = onSelect
  onMeasureRef.current = onMeasure

  // --- Création (une fois) ---
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined
    const map = L.map(containerRef.current, { zoomControl: false, preferCanvas: true, attributionControl: true })
    mapRef.current = map
    map.setView([5.35, -4.01], 12)
    map.attributionControl.setPosition('bottomleft')

    baseRef.current = L.tileLayer(BASEMAPS.standard.url, BASEMAPS.standard.options).addTo(map)
    featureLayerRef.current = L.layerGroup().addTo(map)
    lastFitRef.current = null

    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(containerRef.current)

    // Clic carte pendant une mesure → ajoute un point.
    map.on('click', (e) => {
      const m = measureRef.current
      if (!m) return
      m.points.push(e.latlng)
      redrawMeasure()
    })

    // API impérative pour le rail de contrôle.
    const api = {
      zoomIn: () => map.zoomIn(),
      zoomOut: () => map.zoomOut(),
      resetView: () => fitToFeatures(),
      locate: () => {
        map.locate({ setView: true, maxZoom: 16 })
        map.once('locationfound', (e) => {
          if (locateRef.current) map.removeLayer(locateRef.current)
          locateRef.current = L.circleMarker(e.latlng, {
            radius: 8, color: '#2563eb', fillColor: '#3b82f6', fillOpacity: 0.9, weight: 3,
          }).addTo(map).bindPopup('Ma position').openPopup()
        })
      },
      fullscreen: () => {
        const el = containerRef.current?.closest('[data-map-root]') || containerRef.current
        if (!document.fullscreenElement) el?.requestFullscreen?.()
        else document.exitFullscreen?.()
        setTimeout(() => map.invalidateSize(), 300)
      },
      startMeasure: (type) => {
        clearMeasure()
        measureRef.current = { type, points: [], layer: null, tip: null }
        onMeasureRef.current?.({ active: true, type, text: type === 'area' ? 'Cliquez pour tracer une surface' : 'Cliquez pour tracer une distance' })
      },
      clearMeasure,
      print: () => window.print(),
      invalidate: () => map.invalidateSize(),
      toggleMinimap: (on) => toggleMinimap(on),
    }
    onReady?.(api)

    function redrawMeasure() {
      const m = measureRef.current
      if (!m) return
      if (m.layer) map.removeLayer(m.layer)
      if (m.tip) map.removeLayer(m.tip)
      const latlngs = m.points
      if (latlngs.length < 1) return
      const coords = latlngs.map((p) => [p.lng, p.lat])
      let text = ''
      if (m.type === 'area') {
        m.layer = L.polygon(latlngs, { color: '#e2571e', weight: 2, fillOpacity: 0.15, dashArray: '4 4' }).addTo(map)
        if (latlngs.length >= 3) {
          const poly = turf.polygon([[...coords, coords[0]]])
          const a = turf.area(poly)
          text = a > 10000 ? `${(a / 10000).toFixed(2)} ha` : `${Math.round(a)} m²`
        }
      } else {
        m.layer = L.polyline(latlngs, { color: '#e2571e', weight: 3 }).addTo(map)
        if (latlngs.length >= 2) {
          const line = turf.lineString(coords)
          const km = turf.length(line, { units: 'kilometers' })
          text = km >= 1 ? `${km.toFixed(2)} km` : `${Math.round(km * 1000)} m`
        }
      }
      if (text) {
        m.tip = L.marker(latlngs[latlngs.length - 1], {
          icon: L.divIcon({ className: 'measure-label', html: text, iconSize: null }),
        }).addTo(map)
        onMeasureRef.current?.({ active: true, type: m.type, text })
      }
    }

    function clearMeasure() {
      const m = measureRef.current
      if (m) {
        if (m.layer) map.removeLayer(m.layer)
        if (m.tip) map.removeLayer(m.tip)
      }
      measureRef.current = null
      onMeasureRef.current?.({ active: false })
    }

    function toggleMinimap(on) {
      if (on && !miniRef.current && L.Control.MiniMap) {
        const layer = L.tileLayer(BASEMAPS.clair.url, { ...BASEMAPS.clair.options, attribution: '' })
        miniRef.current = new L.Control.MiniMap(layer, {
          position: 'bottomright', toggleDisplay: true, width: 170, height: 120, zoomLevelOffset: -5,
        }).addTo(map)
      } else if (!on && miniRef.current) {
        map.removeControl(miniRef.current)
        miniRef.current = null
      }
    }

    map._measureRedraw = redrawMeasure
    return () => {
      observer.disconnect()
      map.remove()
      mapRef.current = null
      lastFitRef.current = null
    }
  }, [])

  function fitToFeatures() {
    const map = mapRef.current
    const group = featureLayerRef.current
    if (!map || !group) return
    const layers = []
    group.eachLayer((l) => layers.push(l))
    if (!layers.length) { map.setView([5.35, -4.01], 12); return }
    try {
      const b = L.featureGroup(layers).getBounds()
      if (b.isValid()) map.fitBounds(b, { padding: [50, 50], maxZoom: 18 })
    } catch { /* noop */ }
  }

  // --- Fond de carte ---
  // On ajoute le nouveau fond SOUS l'ancien puis on retire l'ancien SEULEMENT
  // quand le nouveau a chargé (transition douce). Si le fournisseur échoue,
  // on retire le nouveau et on garde l'ancien : la carte n'est jamais vide.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return undefined
    const def = BASEMAPS[basemap] || BASEMAPS.standard
    const prev = baseRef.current
    const next = L.tileLayer(def.url, { ...def.options, zIndex: 100 })
    let done = false
    const swap = () => {
      if (done) return
      done = true
      baseRef.current = next
      if (prev && prev !== next) map.removeLayer(prev)
    }
    const revert = () => {
      if (done) return
      done = true
      map.removeLayer(next)
    }
    next.on('load', swap)
    let errors = 0
    next.on('tileerror', () => { errors += 1; if (errors >= 4) revert() })
    next.addTo(map)
    // Si aucun tuile ne charge à temps, on garde l'ancien fond.
    const t = setTimeout(() => { if (!done) revert() }, 6000)
    return () => clearTimeout(t)
  }, [basemap])

  // --- Orthophoto overlay ---
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (orthoRef.current) { map.removeLayer(orthoRef.current); orthoRef.current = null }
    if (orthoLayer?.tiles_url) {
      orthoRef.current = L.tileLayer(orthoLayer.tiles_url, {
        minZoom: Math.max(1, (orthoLayer.min_zoom || 15) - 3),
        maxZoom: Math.max(orthoLayer.max_zoom || 22, 19),
        minNativeZoom: orthoLayer.min_zoom || 15,
        maxNativeZoom: orthoLayer.max_zoom || 22,
        opacity: orthoOpacity, zIndex: 250,
      }).addTo(map)
    }
  }, [orthoLayer?.tiles_url])
  useEffect(() => { if (orthoRef.current) orthoRef.current.setOpacity(orthoOpacity) }, [orthoOpacity])

  // --- Features ---
  useEffect(() => {
    const map = mapRef.current
    const group = featureLayerRef.current
    if (!map || !group) return
    group.clearLayers()
    layerByUidRef.current = new Map()
    if (layerStyle === 'none') return

    const withLabels = layerStyle === 'noms' && assets.length <= 700
    const useCluster = layerStyle === 'reperes'

    let cluster = null
    if (useCluster) {
      cluster = L.markerClusterGroup({
        chunkedLoading: true, maxClusterRadius: 55, showCoverageOnHover: false,
        iconCreateFunction: (c) => L.divIcon({
          className: 'marker-cluster-kaydan',
          html: `<div>${c.getChildCount()}</div>`,
          iconSize: [44, 44],
        }),
      })
    }

    assets.forEach((feat) => {
      let layer = null
      if (useCluster) {
        const center = Array.isArray(feat.center) ? feat.center
          : (feat.geometry ? centroidOf(feat.geometry) : null)
        if (!center) return
        layer = L.marker(center, { icon: markerIcon(feat) })
      } else if (feat.geometry) {
        layer = L.geoJSON(feat.geometry, {
          style: { color: feat.color || '#e2571e', weight: 1, fillColor: feat.color || '#e2571e', fillOpacity: feat.fillOpacity ?? 0.7 },
        })
      } else if (Array.isArray(feat.center)) {
        layer = L.circleMarker(feat.center, { radius: 6, color: feat.color || '#e2571e', fillColor: feat.color || '#e2571e', fillOpacity: 0.8 })
      }
      if (!layer) return
      layer.on('click', () => onSelectRef.current?.(feat))
      if (withLabels) {
        layer.bindTooltip(chipHtml(feat), { permanent: true, direction: 'center', className: 'lot-chip', opacity: 1 })
        layer.on('add', () => { const el = layer.getTooltip()?.getElement(); if (el) el.style.background = priorityBg(feat) })
      } else {
        layer.bindTooltip(`${feat.name || '—'} · ${feat.status || ''}`, { sticky: true, direction: 'top' })
      }
      layer._featUid = feat.uid
      layerByUidRef.current.set(feat.uid, layer)
      if (cluster) cluster.addLayer(layer); else group.addLayer(layer)
    })
    if (cluster) group.addLayer(cluster)
  }, [assets, layerStyle])

  // --- Sélection ---
  useEffect(() => {
    layerByUidRef.current.forEach((layer, uid) => {
      const setStyle = layer.setStyle?.bind(layer)
      const feat = assets.find((a) => a.uid === uid)
      const selected = uid === selectedUid
      if (setStyle) {
        setStyle({ weight: selected ? 3 : 1, color: selected ? '#0f172a' : (feat?.color || '#e2571e') })
        if (selected) layer.bringToFront?.()
      }
    })
  }, [selectedUid, assets])

  // --- Recadrage (fitToken) ---
  useEffect(() => {
    const map = mapRef.current
    const group = featureLayerRef.current
    if (!map || !group || fitToken === lastFitRef.current) return
    const layers = []
    group.eachLayer((l) => { if (l.eachLayer) l.eachLayer((c) => layers.push(c)); else layers.push(l) })
    if (!layers.length) return
    try {
      const b = L.featureGroup(layers).getBounds()
      if (b.isValid()) { map.fitBounds(b, { padding: [50, 50], maxZoom: 18 }); lastFitRef.current = fitToken }
    } catch { /* noop */ }
  }, [fitToken, assets])

  return <div ref={containerRef} className="h-full w-full" />
}

function centroidOf(geometry) {
  try {
    const c = turf.centroid(geometry)
    const [lng, lat] = c.geometry.coordinates
    return [lat, lng]
  } catch { return null }
}
