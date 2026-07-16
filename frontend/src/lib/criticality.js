// Couleurs / libellés des niveaux de criticité (IDCP, alertes, santé).
export const LEVELS = {
  CRITIQUE: { label: 'Critique', bg: 'bg-rose-100', text: 'text-rose-700', dot: '#e11d48' },
  ELEVE: { label: 'Élevé', bg: 'bg-orange-100', text: 'text-orange-700', dot: '#ea580c' },
  MOYEN: { label: 'Moyen', bg: 'bg-amber-100', text: 'text-amber-700', dot: '#d97706' },
  FAIBLE: { label: 'Faible', bg: 'bg-emerald-100', text: 'text-emerald-700', dot: '#059669' },
  INFO: { label: 'Info', bg: 'bg-sky-100', text: 'text-sky-700', dot: '#0284c7' },
}

export function levelStyle(key) {
  return LEVELS[key] || LEVELS.INFO
}

// Bandes du score de santé programme (0–100).
export function bandStyle(band) {
  switch (band) {
    case 'Excellent': return { text: 'text-emerald-700', bar: '#059669' }
    case 'Bon': return { text: 'text-lime-700', bar: '#65a30d' }
    case 'Sous surveillance': return { text: 'text-amber-700', bar: '#d97706' }
    case 'Critique': return { text: 'text-orange-700', bar: '#ea580c' }
    default: return { text: 'text-rose-700', bar: '#e11d48' } // Urgence
  }
}
