import { useEffect, useRef } from 'react'
import L from 'leaflet'

/**
 * Canvas Leaflet pour la carte parcellaire. Piloté par props, sans état
 * interne React (Leaflet gère son propre cycle de vie via des refs).
 *
 * Props :
 *  - assets        : features renvoyées par l'API map (geometry + center + color)
 *  - selectedUid   : uid de la feature sélectionnée (surbrillance)
 *  - onSelect(feat): clic sur une feature
 *  - onViewportChange({bbox, zoom}) : après un déplacement (moveend), debounced côté parent
 *  - orthoLayer    : {tiles_url, min_zoom, max_zoom} | null — couche orthophoto à superposer
 *  - orthoOpacity  : opacité de la couche orthophoto (0..1)
 *  - fitToken      : quand cette valeur change, on recadre sur les features
 *
 * Rendu : polygones GeoJSON quand la géométrie est présente (zoom ≥ 14),
 * sinon un cercle au centre. Les couleurs viennent de l'API (color /
 * fillOpacity) — le front ne réinvente pas le mapping des statuts.
 */
export default function MapCanvas({
  assets = [],
  selectedUid = null,
  onSelect,
  onViewportChange,
  orthoLayer = null,
  orthoOpacity = 1,
  fitToken = '',
}) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const featureLayerRef = useRef(null)
  const orthoLayerRef = useRef(null)
  const layerByUidRef = useRef(new Map())
  const onSelectRef = useRef(onSelect)
  const onViewportRef = useRef(onViewportChange)
  const lastFitTokenRef = useRef(null)

  onSelectRef.current = onSelect
  onViewportRef.current = onViewportChange

  // --- Création de la carte (une fois) ---
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined

    const map = L.map(containerRef.current, { zoomControl: true, preferCanvas: true })
    mapRef.current = map
    map.setView([5.35, -4.01], 12) // Abidjan par défaut

    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 22, maxNativeZoom: 19, attribution: '© OpenStreetMap',
    })
    const carto = L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
      { maxZoom: 22, maxNativeZoom: 20, attribution: '© OpenStreetMap © CARTO' },
    )
    osm.addTo(map)
    L.control.layers(
      { 'Plan OSM': osm, 'Plan clair (CARTO)': carto },
      {},
      { position: 'topright', collapsed: true },
    ).addTo(map)

    featureLayerRef.current = L.layerGroup().addTo(map)

    let moveTimer = null
    map.on('moveend zoomend', () => {
      if (!onViewportRef.current) return
      clearTimeout(moveTimer)
      moveTimer = setTimeout(() => {
        const b = map.getBounds()
        onViewportRef.current({
          bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].join(','),
          zoom: map.getZoom(),
        })
      }, 400)
    })

    // Recadrage fiable même si le conteneur n'a pas encore sa taille.
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(containerRef.current)

    return () => {
      clearTimeout(moveTimer)
      observer.disconnect()
      map.remove()
      mapRef.current = null
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
      }).addTo(map)
      orthoLayerRef.current.bringToFront()
    }
  }, [orthoLayer?.tiles_url])

  useEffect(() => {
    if (orthoLayerRef.current) orthoLayerRef.current.setOpacity(orthoOpacity)
  }, [orthoOpacity])

  // --- Couche des features (parcelles / lots) ---
  useEffect(() => {
    const map = mapRef.current
    const group = featureLayerRef.current
    if (!map || !group) return

    group.clearLayers()
    layerByUidRef.current = new Map()

    assets.forEach((feat) => {
      const baseStyle = {
        color: feat.color || '#38bdf8',
        weight: 1,
        fillColor: feat.color || '#38bdf8',
        fillOpacity: feat.fillOpacity ?? 0.7,
      }
      let layer = null
      if (feat.geometry) {
        layer = L.geoJSON(feat.geometry, { style: baseStyle })
      } else if (Array.isArray(feat.center) && feat.center.length === 2) {
        layer = L.circleMarker(feat.center, { radius: 6, ...baseStyle })
      }
      if (!layer) return
      layer.on('click', () => onSelectRef.current && onSelectRef.current(feat))
      layer.bindTooltip(
        `${feat.name || '—'} · ${feat.status || ''}`,
        { sticky: true, direction: 'top' },
      )
      layer._featUid = feat.uid
      group.addLayer(layer)
      layerByUidRef.current.set(feat.uid, layer)
    })
  }, [assets])

  // --- Surbrillance de la sélection ---
  useEffect(() => {
    layerByUidRef.current.forEach((layer, uid) => {
      const selected = uid === selectedUid
      const setStyle = layer.setStyle?.bind(layer)
      if (!setStyle) return
      const feat = assets.find((a) => a.uid === uid)
      setStyle({
        weight: selected ? 3 : 1,
        color: selected ? '#0f172a' : (feat?.color || '#38bdf8'),
        fillOpacity: selected ? Math.min((feat?.fillOpacity ?? 0.7) + 0.15, 1) : (feat?.fillOpacity ?? 0.7),
      })
      if (selected) layer.bringToFront?.()
    })
  }, [selectedUid, assets])

  // --- Recadrage sur changement de filtres (fitToken) ---
  // On ne marque le jeton « consommé » qu'APRÈS un recadrage effectif :
  // au premier rendu les features ne sont pas encore chargées (group vide),
  // et il faut donc attendre leur arrivée (nouveau passage via la dép
  // `assets`) pour cadrer — sinon la carte reste sur la vue par défaut.
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
      /* géométries partielles : on laisse la vue courante */
    }
  }, [fitToken, assets])

  return <div ref={containerRef} className="h-full w-full" />
}
