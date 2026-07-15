/**
 * Endpoints orthophotos.
 *
 * Deux familles :
 *  - /api/orthophotos/...      → API DRF ajoutée pour le SPA
 *  - /orthophotos/...          → endpoints JSON historiques (upload S3
 *    multipart + polling statut), réutilisés tels quels.
 */
import { request } from './client'

export function listOrthophotos(params = {}, { signal } = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined),
  )
  const qs = query.toString()
  return request(`/api/orthophotos/${qs ? `?${qs}` : ''}`, { signal })
}

export function getOrthophoto(id, { signal } = {}) {
  return request(`/api/orthophotos/${id}/`, { signal })
}

export function getReferenceData() {
  return request('/api/orthophotos/reference-data/')
}

export function retryOrthophoto(id) {
  return request(`/api/orthophotos/${id}/retry/`, { method: 'POST' })
}

export function setCurrentOrthophoto(id) {
  return request(`/api/orthophotos/${id}/set-current/`, { method: 'POST' })
}

export function deleteOrthophotoTiles(id) {
  return request(`/api/orthophotos/${id}/delete-tiles/`, { method: 'POST' })
}

/** Polling léger (endpoint historique, ~50 derniers logs). */
export function getOrthophotoStatus(id, { signal } = {}) {
  return request(`/orthophotos/${id}/status/`, { signal })
}

export function logsDownloadUrl(id) {
  return `/orthophotos/${id}/logs.txt`
}

// ------- Upload multipart S3 (MinIO) -------

export function uploadInit(payload) {
  return request('/orthophotos/upload/init/', { method: 'POST', json: payload })
}

export function uploadComplete(payload) {
  return request('/orthophotos/upload/complete/', { method: 'POST', json: payload })
}

export function uploadAbort(orthophotoId) {
  return request('/orthophotos/upload/abort/', {
    method: 'POST',
    json: { orthophoto_id: orthophotoId },
  })
}
