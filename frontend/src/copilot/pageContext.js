import { useEffect } from 'react'

// Contexte de page partagé, lu par le CopilotPanel à chaque message.
// La route vient toujours du hash ; les pages enrichissent (program_id…).
let extra = {}
// Fournisseur dynamique : renvoie des champs LIVE calculés à l'envoi du message
// (ex. emprise carte courante) sans re-rendre la page à chaque déplacement.
let dynamicProvider = null

export function setCopilotContext(next) {
  extra = next || {}
}

export function setCopilotContextProvider(fn) {
  dynamicProvider = typeof fn === 'function' ? fn : null
}

export function getCopilotContext() {
  const route = (window.location.hash || '#/').replace(/^#/, '') || '/'
  let live = {}
  try { live = dynamicProvider ? (dynamicProvider() || {}) : {} } catch { live = {} }
  // On retire les valeurs vides pour ne pas polluer le contexte serveur.
  const merged = { route, ...extra, ...live }
  return Object.fromEntries(Object.entries(merged).filter(([, v]) => v != null && v !== ''))
}

// Hook que chaque page appelle pour déclarer son contexte métier (statique).
export function useCopilotContext(next) {
  const key = JSON.stringify(next || {})
  useEffect(() => {
    setCopilotContext(next)
    return () => setCopilotContext({})
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps
}

// Hook pour un contexte LIVE (recalculé à chaque message). `fn` doit lire des
// refs/état courants ; on ré-enregistre quand `deps` change (closure fraîche).
export function useCopilotContextProvider(fn, deps) {
  useEffect(() => {
    setCopilotContextProvider(fn)
    return () => setCopilotContextProvider(null)
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
}

// Suggestions contextuelles selon la page ouverte (amorces cliquables).
const SUGGESTIONS = [
  [/^\/(carte)?$/, [
    'Centre la carte sur un programme',
    'Quels programmes à moins de 3 km d\'un hôpital ?',
    'Passe la carte en vue satellite',
  ]],
  [/^\/dashboard/, [
    'Fais l\'analyse du tableau de bord',
    'Combien de parcelles disponibles ?',
    'Prépare le rapport PDF du tableau de bord',
  ]],
  [/^\/pilotage\/risques/, [
    'Liste les clients à risque',
    'Exporte les clients à risque en Excel',
    'Quels clients ont payé plus de 90 % ?',
  ]],
  [/^\/orthophotos/, [
    'Quels programmes sans orthophoto ?',
    'Relance l\'orthophoto en échec de Callisto',
    'Affiche l\'orthophoto d\'un programme',
  ]],
]

export function getCopilotSuggestions() {
  const route = (window.location.hash || '#/').replace(/^#/, '') || '/'
  for (const [re, items] of SUGGESTIONS) {
    if (re.test(route)) return items
  }
  return [
    'Recherche un programme ou une parcelle',
    'Résume le tableau de bord',
    'Prépare un rapport',
  ]
}
