import { useEffect, useRef } from 'react'
import L from 'leaflet'

/**
 * Aperçu Leaflet des tuiles XYZ générées par le pipeline GDAL.
 * Fond OSM + couche orthophoto ; cadré sur `bounds` si fourni
 * ([[south, west], [north, east]], format renvoyé par l'API).
 */
export default function TileMapPreview({ tilesUrl, bounds, minZoom = 15, maxZoom = 22 }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current || !tilesUrl) return undefined

    const map = L.map(containerRef.current, { zoomControl: true })
    mapRef.current = map

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    }).addTo(map)

    // min/maxNativeZoom = plage réellement générée par gdal2tiles ;
    // en dehors, Leaflet réutilise les tuiles existantes en les
    // redimensionnant au lieu de requêter des PNG 404.
    L.tileLayer(tilesUrl, {
      minZoom: Math.max(1, minZoom - 3),
      maxZoom: Math.max(maxZoom, 19),
      minNativeZoom: minZoom,
      maxNativeZoom: maxZoom,
      opacity: 1,
    }).addTo(map)

    if (bounds) {
      map.fitBounds(bounds)
      L.rectangle(bounds, { color: '#0284c7', weight: 1, fill: false, dashArray: '4 4' }).addTo(map)
    } else {
      map.setView([5.35, -4.01], minZoom) // Abidjan par défaut
    }

    // Leaflet fige la taille du conteneur à la construction ; si React
    // n'a pas encore layouté (taille 0), fitBounds retombe sur zoom 0
    // (mappemonde). On recale une fois le layout stabilisé.
    const settle = setTimeout(() => {
      map.invalidateSize()
      if (bounds) map.fitBounds(bounds)
    }, 50)

    return () => {
      clearTimeout(settle)
      map.remove()
      mapRef.current = null
    }
  }, [tilesUrl, JSON.stringify(bounds), minZoom, maxZoom])

  if (!tilesUrl) return null
  return <div ref={containerRef} className="h-96 w-full overflow-hidden rounded-xl border border-slate-200" />
}
