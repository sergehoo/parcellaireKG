/**
 * Client HTTP minimal pour l'API Django.
 *
 * - Authentification par session (mêmes cookies que le site Django).
 * - CSRF : le cookie `csrftoken` est posé par GET /api/orthophotos/csrf/
 *   puis renvoyé dans l'en-tête X-CSRFToken sur chaque requête non-GET.
 * - Session expirée (401) → on notifie le garde d'authentification React
 *   (AuthProvider), qui réaffiche la page de connexion React. Plus aucune
 *   redirection vers une page HTML Django.
 */

export function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[2]) : null
}

let csrfReady = null

export function ensureCsrf() {
  if (!csrfReady) {
    // IMPORTANT : un échec doit REJETER (et ne pas être mis en cache), sinon
    // le POST suivant part avec un X-CSRFToken vide → 403 CSRF opaque.
    // fetch() ne rejette pas sur un statut HTTP d'erreur : on vérifie
    // explicitement response.ok ET la présence réelle du cookie.
    csrfReady = (async () => {
      const response = await fetch('/api/orthophotos/csrf/', { credentials: 'same-origin' })
      if (!response.ok) {
        throw new ApiError(
          `Impossible d'obtenir le jeton de sécurité (HTTP ${response.status}).`,
          { status: response.status },
        )
      }
      if (!getCookie('csrftoken')) {
        throw new ApiError(
          "Le jeton de sécurité n'a pas été posé par le navigateur (cookies bloqués ?).",
          { status: 0 },
        )
      }
      return true
    })().catch((err) => {
      csrfReady = null // on retentera au prochain appel
      throw err
    })
  }
  return csrfReady
}

// Le garde d'authentification (AuthProvider) enregistre ici son gestionnaire
// pour repasser le SPA en état « non authentifié » (page de login React).
let unauthorizedHandler = null
export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = fn
}
export function handleUnauthorized() {
  if (unauthorizedHandler) unauthorizedHandler()
}

export class ApiError extends Error {
  constructor(message, { status, data } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export async function request(url, { method = 'GET', json, signal } = {}) {
  const headers = { Accept: 'application/json' }
  const options = { method, credentials: 'same-origin', headers, signal }

  if (method !== 'GET') {
    await ensureCsrf()
    headers['X-CSRFToken'] = getCookie('csrftoken') || ''
  }
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(json)
  }

  const response = await fetch(url, options)

  // 401 = pas authentifié → réafficher la connexion React. On NE bascule PAS
  // sur 403 : DRF renvoie 403 aussi bien pour une permission métier manquante
  // que pour une session expirée, et cela créerait une boucle. Le 403 remonte
  // donc comme une erreur normale (toast affiché par l'appelant).
  if (response.status === 401) {
    handleUnauthorized()
    throw new ApiError('Session expirée', { status: 401 })
  }

  let data = null
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    data = await response.json()
  }

  if (!response.ok) {
    const message = (data && (data.error || data.detail)) || `Erreur HTTP ${response.status}`
    throw new ApiError(message, { status: response.status, data })
  }
  return data
}

/**
 * Télécharge un fichier (ex. export CSV) via fetch authentifié puis déclenche
 * l'enregistrement navigateur. Le nom vient de l'en-tête Content-Disposition
 * si présent, sinon de `fallbackName`.
 */
export async function downloadFile(url, fallbackName = 'export.csv') {
  const response = await fetch(url, { credentials: 'same-origin' })
  if (response.status === 401) {
    handleUnauthorized()
    throw new ApiError('Session expirée', { status: 401 })
  }
  if (!response.ok) {
    throw new ApiError(`Erreur HTTP ${response.status}`, { status: response.status })
  }
  const blob = await response.blob()
  const cd = response.headers.get('content-disposition') || ''
  const match = cd.match(/filename="?([^"]+)"?/)
  const name = match ? match[1] : fallbackName
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(objectUrl)
}
