const MONTHS_FR = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

export function monthName(month) {
  return MONTHS_FR[month - 1] || String(month)
}

/**
 * Rend une valeur de synthèse compacte à partir d'une chaîne renvoyée par
 * l'API : montants abrégés (« 62 819 098 749 FCFA » → « 62,8 Md FCFA »),
 * comptes avec séparateur de milliers (« 1444 » → « 1 444 »). Les valeurs
 * non numériques (« Masqué », « — ») sont renvoyées telles quelles.
 */
export function compactStat(value) {
  if (value === null || value === undefined) return '—'
  const str = String(value)
  const digits = (str.match(/\d/g) || []).join('')
  if (!digits) return str
  const n = Number(digits)
  const isMoney = /fcfa|€|\$/i.test(str)
  if (isMoney) {
    if (n >= 1e9) return `${(n / 1e9).toFixed(1).replace('.', ',')} Md FCFA`
    if (n >= 1e6) return `${(n / 1e6).toFixed(1).replace('.', ',')} M FCFA`
    if (n >= 1e3) return `${Math.round(n / 1e3)} k FCFA`
    return `${n.toLocaleString('fr-FR')} FCFA`
  }
  return n.toLocaleString('fr-FR')
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
