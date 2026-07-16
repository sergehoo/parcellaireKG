/**
 * Client générique pour l'API CRUD (/api/crud/<resource>/) et le
 * tableau de bord. Utilisé par le framework de pages ResourceList /
 * ResourceDetail / ResourceForm.
 */
import { request } from './client'

const BASE = '/api/crud'

export function listResource(endpoint, params = {}, { signal } = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined),
  )
  const qs = query.toString()
  return request(`${BASE}/${endpoint}/${qs ? `?${qs}` : ''}`, { signal })
}

export function getResource(endpoint, id, { signal } = {}) {
  return request(`${BASE}/${endpoint}/${id}/`, { signal })
}

export function createResource(endpoint, payload) {
  return request(`${BASE}/${endpoint}/`, { method: 'POST', json: payload })
}

export function updateResource(endpoint, id, payload) {
  return request(`${BASE}/${endpoint}/${id}/`, { method: 'PATCH', json: payload })
}

export function deleteResource(endpoint, id) {
  return request(`${BASE}/${endpoint}/${id}/`, { method: 'DELETE' })
}

export function getOptions() {
  return request(`${BASE}/options/`)
}

export function getDashboard({ signal } = {}) {
  return request('/api/dashboard/', { signal })
}
