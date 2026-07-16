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
      L.rectangle(bounds, { color: '#0284c7', weight: 1, fill: false, dashArray: '4 4' }).addTo(map)
    }

    // Cadrage. PIÈGE Leaflet : si le conteneur a une taille nulle au
    // moment du fitBounds (layout React pas encore appliqué), le zoom
    // calculé retombe à 0 (mappemonde) et n'est jamais recalculé. Un
    // délai fixe est trop fragile ; on cadre donc dès que le conteneur
    // a une taille réelle, via ResizeObserver, puis on se désabonne.
    let framed = false
    const frame = () => {
      const el = containerRef.current
      if (framed || !el || el.offsetWidth === 0 || el.offsetHeight === 0) return
      framed = true
      map.invalidateSize()
      if (bounds) map.fitBounds(bounds, { maxZoom })
      else map.setView([5.35, -4.01], minZoom) // Abidjan par défaut
      observer.disconnect()
    }
    const observer = new ResizeObserver(frame)
    observer.observe(containerRef.current)
    frame() // cas où le conteneur a déjà sa taille au montage

    return () => {
      observer.disconnect()
      map.remove()
      mapRef.current = null
    }
  }, [tilesUrl, JSON.stringify(bounds), minZoom, maxZoom])

  if (!tilesUrl) return null
  return <div ref={containerRef} className="h-96 w-full overflow-hidden rounded-xl border border-slate-200" />
}
