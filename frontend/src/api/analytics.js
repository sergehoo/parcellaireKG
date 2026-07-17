import { request } from './client'

export function getAnalyticsDashboard({ signal } = {}) {
  return request('/api/analytics/dashboard/', { signal })
}

export function getAtRisk(params = {}, { signal } = {}) {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined),
  ).toString()
  return request(`/api/analytics/at-risk/${q ? `?${q}` : ''}`, { signal })
}

export function getAlerts(params = {}, { signal } = {}) {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined),
  ).toString()
  return request(`/api/alerts/${q ? `?${q}` : ''}`, { signal })
}

export function alertAction(id, action) {
  return request(`/api/alerts/${id}/${action}/`, { method: 'POST' })
}

// Compteurs d'alertes actives par niveau — endpoint léger pour le badge nav.
export function getAlertSummary({ signal } = {}) {
  return request('/api/alerts/summary/', { signal })
}

// Recalcul à la demande (async via Celery, ou synchrone si broker injoignable).
export function regenerateAlerts() {
  return request('/api/alerts/regenerate/', { method: 'POST' })
}
