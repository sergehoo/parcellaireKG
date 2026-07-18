import { downloadFile, request } from './client'

// Construit une querystring en ignorant les valeurs vides/nulles.
function toQuery(params) {
  const q = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined),
  ).toString()
  return q ? `?${q}` : ''
}

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

// Sévérité d'alerte active par parcelle/programme, pour surligner la carte.
export function getAlertMap({ signal } = {}) {
  return request('/api/alerts/map/?levels=CRITIQUE,ELEVE', { signal })
}

// Recalcul à la demande (async via Celery, ou synchrone si broker injoignable).
export function regenerateAlerts() {
  return request('/api/alerts/regenerate/', { method: 'POST' })
}

// Exports CSV (téléchargement navigateur). Respectent les filtres passés.
export function exportAtRisk(params = {}) {
  return downloadFile(`/api/analytics/at-risk/export/${toQuery(params)}`, 'clients-a-risque.csv')
}

export function exportAlerts(params = {}) {
  return downloadFile(`/api/alerts/export/${toQuery(params)}`, 'alertes.csv')
}

// Rapport PDF exécutif du Centre de pilotage (WeasyPrint côté serveur).
export function exportDashboardReport() {
  return downloadFile('/api/analytics/dashboard/report/', 'tableau-de-bord.pdf')
}
