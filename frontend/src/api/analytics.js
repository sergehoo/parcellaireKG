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
