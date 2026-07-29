import { useEffect } from 'react'

// Contexte de page partagé, lu par le CopilotPanel à chaque message.
// La route vient toujours du hash ; les pages enrichissent (program_id…).
let extra = {}

export function setCopilotContext(next) {
  extra = next || {}
}

export function getCopilotContext() {
  const route = (window.location.hash || '#/').replace(/^#/, '') || '/'
  return { route, ...extra }
}

// Hook que chaque page appelle pour déclarer son contexte métier.
export function useCopilotContext(next) {
  const key = JSON.stringify(next || {})
  useEffect(() => {
    setCopilotContext(next)
    return () => setCopilotContext({})
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps
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
