import { ensureCsrf, request } from './client'

// Utilisateur courant (nom, e-mail, initiales, droits) pour la barre du SPA.
export function getMe({ signal } = {}) {
  return request('/api/auth/me/', { signal })
}

// Connexion par session, 100 % API (aucune page HTML Django).
export async function login(username, password) {
  await ensureCsrf()
  return request('/api/auth/login/', { method: 'POST', json: { username, password } })
}

// Déconnexion via l'API (ferme la session côté Django).
export async function logout() {
  try {
    await request('/api/auth/logout/', { method: 'POST' })
  } catch (_) {
    // session déjà close / réseau : on considère l'utilisateur déconnecté.
  }
}

// Changement de mot de passe (utilisateur authentifié).
export function changePassword(currentPassword, newPassword) {
  return request('/api/auth/password/', {
    method: 'POST',
    json: { current_password: currentPassword, new_password: newPassword },
  })
}
