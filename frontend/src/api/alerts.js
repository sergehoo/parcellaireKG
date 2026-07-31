// Client de l'API du module d'alertes (/api/alerts/*).
import { request } from './client'

const BASE = '/api/alerts'

const qs = (params = {}) => {
  const s = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined),
  ).toString()
  return s ? `?${s}` : ''
}

export const getAlertDashboard = ({ signal } = {}) => request(`${BASE}/dashboard/`, { signal })

export const listConfigurations = ({ signal } = {}) => request(`${BASE}/configurations/`, { signal })
export const createConfiguration = (payload) => request(`${BASE}/configurations/`, { method: 'POST', json: payload })
export const updateConfiguration = (id, payload) => request(`${BASE}/configurations/${id}/`, { method: 'PATCH', json: payload })
export const deleteConfiguration = (id) => request(`${BASE}/configurations/${id}/`, { method: 'DELETE' })

export const listRecipients = ({ signal } = {}) => request(`${BASE}/recipients/`, { signal })
export const createRecipient = (payload) => request(`${BASE}/recipients/`, { method: 'POST', json: payload })
export const deleteRecipient = (id) => request(`${BASE}/recipients/${id}/`, { method: 'DELETE' })

export const listGroups = ({ signal } = {}) => request(`${BASE}/groups/`, { signal })

export const listDetections = (params = {}, { signal } = {}) => request(`${BASE}/detections/${qs(params)}`, { signal })
export const acknowledgeDetection = (id) => request(`${BASE}/detections/${id}/acknowledge/`, { method: 'POST' })

export const listHistory = ({ signal } = {}) => request(`${BASE}/history/`, { signal })

export const generateReport = (payload) => request(`${BASE}/reports/generate/`, { method: 'POST', json: payload })
export const smtpTest = (email) => request(`${BASE}/smtp/test/`, { method: 'POST', json: { email } })

export const downloadReportUrl = (reportId) => `${BASE}/reports/${reportId}/download/`
