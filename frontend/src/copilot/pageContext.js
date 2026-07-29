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
