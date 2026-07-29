import { request } from './client'

// Envoie un message au Copilote IA. `context` décrit la page courante ;
// le backend le ré-résout côté serveur (avec masquage).
export function sendCopilotMessage({ message, conversationId, context, model }) {
  return request('/api/copilot/chat/', {
    method: 'POST',
    json: {
      message,
      conversation_id: conversationId || null,
      context: context || {},
      model: model || null,
    },
  })
}
