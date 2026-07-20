import { ensureCsrf, getCookie, request } from './client'

// Utilisateur courant (nom, e-mail, initiales, droits) pour la barre du SPA.
export function getMe({ signal } = {}) {
  return request('/api/auth/me/', { signal })
}

// Déconnexion : POST allauth (avec CSRF), puis retour à la page de login.
export async function logout() {
  await ensureCsrf()
  try {
    await fetch('/accounts/logout/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') || '' },
      credentials: 'same-origin',
    })
  } finally {
    window.location.href = '/accounts/login/'
  }
}
