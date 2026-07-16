import { useEffect, useRef } from 'react'
import L from 'leaflet'

/**
 * Canvas Leaflet de la carte parcellaire. Piloté par props, sans état
 * React interne (Leaflet gère son cycle de vie via des refs).
 *
 * `mode` conditionne le rendu :
 *  - parcelles  : polygones pleins colorés par statut (couleur de l'API)
 *  - noms       : polygones + étiquettes de lot permanentes (T/V/P),
 *                 teintées par priorité travaux
 *  - osm        : contours seuls sur fond OSM
 *  - orthophoto : contours seuls + couche orthophoto
 *  - mixte      : polygones semi-transparents + couche orthophoto
 */

function priorityBg(feat) {
  const p = feat.priority_stats?.priority
  if (p === 'HIGH') return '#7f1d1d'   // red-900
  if (p === 'MEDIUM') return '#78350f' // amber-900
  return '#1e293b'                     // slate-800 (faible / inconnu)
}

function statFragment(feat) {
  const cs = feat.construction_stats || {}
  const fs = feat.financial_stats || {}
  const t = cs.taux_avancement && cs.taux_avancement !== 'Masqué' ? `T:${cs.taux_avancement}` : ''
  const p = fs.taux_paiement && fs.taux_paiement !== 'Masqué' ? `P:${fs.taux_paiement}` : ''
  let v = ''
  const ev = cs.evolution_mensuelle
  if (typeof ev === 'number' && ev !== 0) {
    const cls = ev > 0 ? 'v-pos' : 'v-neg'
    v = `<span class="${cls}">V:${ev > 0 ? '+' : ''}${Math.round(ev)}%</span>`
  }
  return [t, v, p].filter(Boolean).join(' · ')
}

function chipHtml(feat) {
  const stats = statFragment(feat)
  return (
    `<div class="lot-name">${feat.name || '—'}</div>`
    + (stats ? `<div class="lot-stats">${stats}</div>` : '')
  )
}

export default function MapCanvas({
  assets = [],
  selectedUid = null,
  onSelect,
  orthoLayer = null,
  orthoOpacity = 1,
  fitToken = '',
  mode = 'parcelles',
}) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const featureLayerRef = useRef(null)
  const orthoLayerRef = useRef(null)
  const layerByUidRef = useRef(new Map())
  const onSelectRef = useRef(onSelect)
  const lastFitTokenRef = useRef(null)
  onSelectRef.current = onSelect

  // --- Création de la carte (une fois) ---
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined
    // Zoom en bas-droite : la barre d'outils flottante occupe le haut-gauche.
    const map = L.map(containerRef.current, { zoomControl: false, preferCanvas: true })
    mapRef.current = map
    L.control.zoom({ position: 'bottomright' }).addTo(map)
    map.setView([5.35, -4.01], 12)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 22, maxNativeZoom: 19, attribution: '© OpenStreetMap',
    }).addTo(map)

    featureLayerRef.current = L.layerGroup().addTo(map)
    // Nouvelle instance de carte → le recadrage doit pouvoir se rejouer.
    // (Sans ça, le double montage StrictMode « consomme » le jeton sur la
    // 1re carte détruite et la 2e reste sur la vue par défaut.)
    lastFitTokenRef.current = null

    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(containerRef.current)
    return () => {
      observer.disconnect()
      map.remove()
      mapRef.current = null
      lastFitTokenRef.current = null
    }
  }, [])

  // --- Couche orthophoto ---
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (orthoLayerRef.current) {
      map.removeLayer(orthoLayerRef.current)
      orthoLayerRef.current = null
    }
    if (orthoLayer && orthoLayer.tiles_url) {
      orthoLayerRef.current = L.tileLayer(orthoLayer.tiles_url, {
        minZoom: Math.max(1, (orthoLayer.min_zoom || 15) - 3),
        maxZoom: Math.max(orthoLayer.max_zoom || 22, 19),
        minNativeZoom: orthoLayer.min_zoom || 15,
        maxNativeZoom: orthoLayer.max_zoom || 22,
        opacity: orthoOpacity,
        zIndex: 250,
      }).addTo(map)
    }
  }, [orthoLayer?.tiles_url])

  useEffect(() => {
    if (orthoLayerRef.current) orthoLayerRef.current.setOpacity(orthoOpacity)
  }, [orthoOpacity])

  // --- Couche des features + mode d'affichage ---
  useEffect(() => {
    const map = mapRef.current
    const group = featureLayerRef.current
    if (!map || !group) return

    group.clearLayers()
    layerByUidRef.current = new Map()

    const outline = mode === 'osm' || mode === 'orthophoto'
    const fillOp = (feat) => {
      if (outline) return 0
      if (mode === 'mixte') return 0.45
      if (mode === 'noms') return 0.55
      return feat.fillOpacity ?? 0.7
    }
    // Étiquettes permanentes seulement en mode « noms » et si l'ensemble
    // reste raisonnable (sinon des centaines de tooltips figent le rendu).
    const withLabels = mode === 'noms' && assets.length <= 700

    assets.forEach((feat) => {
      const style = {
        color: feat.color || '#e2571e',
        weight: outline ? 1.5 : 1,
        fillColor: feat.color || '#e2571e',
        fillOpacity: fillOp(feat),
      }
      let layer = null
      if (feat.geometry) {
        layer = L.geoJSON(feat.geometry, { style })
      } else if (Array.isArray(feat.center) && feat.center.length === 2) {
        layer = L.circleMarker(feat.center, { radius: 6, ...style })
      }
      if (!layer) return
      layer.on('click', () => onSelectRef.current && onSelectRef.current(feat))

      if (withLabels) {
        layer.bindTooltip(chipHtml(feat), {
          permanent: true,
          direction: 'center',
          className: 'lot-chip',
          opacity: 1,
        })
        // Teinte de priorité posée sur l'élément tooltip après ajout.
        layer.on('add', () => {
          const el = layer.getTooltip()?.getElement()
          if (el) el.style.background = priorityBg(feat)
        })
      } else {
        layer.bindTooltip(`${feat.name || '—'} · ${feat.status || ''}`, {
          sticky: true, direction: 'top',
        })
      }

      layer._featUid = feat.uid
      group.addLayer(layer)
      layerByUidRef.current.set(feat.uid, layer)
    })
  }, [assets, mode])

  // --- Surbrillance de la sélection ---
  useEffect(() => {
    layerByUidRef.current.forEach((layer, uid) => {
      const setStyle = layer.setStyle?.bind(layer)
      if (!setStyle) return
      const feat = assets.find((a) => a.uid === uid)
      const selected = uid === selectedUid
      setStyle({
        weight: selected ? 3 : (mode === 'osm' || mode === 'orthophoto' ? 1.5 : 1),
        color: selected ? '#0f172a' : (feat?.color || '#e2571e'),
      })
      if (selected) layer.bringToFront?.()
    })
  }, [selectedUid, assets, mode])

  // --- Recadrage sur changement de filtres (fitToken) ---
  // Jeton consommé APRÈS un recadrage effectif : au 1er rendu les features
  // ne sont pas encore chargées (group vide), il faut attendre leur arrivée.
  useEffect(() => {
    const map = mapRef.current
    const group = featureLayerRef.current
    if (!map || !group || fitToken === lastFitTokenRef.current) return
    const layers = []
    group.eachLayer((l) => layers.push(l))
    if (!layers.length) return
    try {
      const bounds = L.featureGroup(layers).getBounds()
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 18 })
        lastFitTokenRef.current = fitToken
      }
    } catch {
      /* géométries partielles : on garde la vue courante */
    }
  }, [fitToken, assets])

  return <div ref={containerRef} className="h-full w-full" />
}
