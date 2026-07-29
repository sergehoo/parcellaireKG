import { request } from './client'

// Envoie un message au Copilote IA. `context` décrit la page courante ;
// le backend le ré-résout côté serveur (avec masquage).
// `confirmAction` {tool, arguments} : exécute une action à effet de bord
// déjà confirmée par l'utilisateur (chemin déterministe hors-LLM côté serveur).
export function sendCopilotMessage({ message, conversationId, context, model, confirmAction }) {
  return request('/api/copilot/chat/', {
    method: 'POST',
    json: {
      message: message || '',
      conversation_id: conversationId || null,
      context: context || {},
      model: model || null,
      confirm_action: confirmAction || null,
    },
  })
}
