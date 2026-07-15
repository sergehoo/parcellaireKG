const MONTHS_FR = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

export function monthName(month) {
  return MONTHS_FR[month - 1] || String(month)
}

export function periodLabel(ortho) {
  if (ortho.period_label) return ortho.period_label
  if (ortho.reference_year && ortho.reference_month) {
    return `${monthName(ortho.reference_month)} ${ortho.reference_year}`
  }
  if (ortho.capture_date) return formatDate(ortho.capture_date)
  return ortho.version || '—'
}

export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '—'
  const units = ['o', 'Ko', 'Mo', 'Go', 'To']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value >= 100 || unit === 0 ? 0 : 1)} ${units[unit]}`
}

export function formatDate(iso) {
  if (!iso) return '—'
  const date = new Date(iso)
  return date.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatDateTime(iso) {
  if (!iso) return '—'
  const date = new Date(iso)
  return date.toLocaleString('fr-FR', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('fr-FR', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}
