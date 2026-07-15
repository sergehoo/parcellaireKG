import { useEffect, useState } from 'react'
import { getReferenceData } from '../api/orthophotos'

/** Projets / programmes / statuts / années — chargés une fois par page. */
export default function useReferenceData() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    getReferenceData()
      .then((payload) => { if (!cancelled) setData(payload) })
      .catch((err) => { if (!cancelled) setError(err) })
    return () => { cancelled = true }
  }, [])

  return { refData: data, refError: error }
}
