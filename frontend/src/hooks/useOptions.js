import { useEffect, useState } from 'react'
import { getOptions } from '../api/resources'

// Options des formulaires/filtres (pays, programmes, statuts, permissions…).
// Mises en cache au niveau du module : chargées une seule fois par session.
let cache = null
let inflight = null

export default function useOptions() {
  const [options, setOptions] = useState(cache)

  useEffect(() => {
    if (cache) { setOptions(cache); return undefined }
    let cancelled = false
    inflight = inflight || getOptions()
    inflight
      .then((data) => { cache = data; if (!cancelled) setOptions(data) })
      .catch(() => {})
      .finally(() => { inflight = null })
    return () => { cancelled = true }
  }, [])

  return options
}
