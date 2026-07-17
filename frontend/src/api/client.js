/**
 * Client HTTP minimal pour l'API Django.
 *
 * - Authentification par session (mêmes cookies que le site Django).
 * - CSRF : le cookie `csrftoken` est posé par GET /api/orthophotos/csrf/
 *   puis renvoyé dans l'en-tête X-CSRFToken sur chaque requête non-GET.
 * - Si la session a expiré, Django renvoie 401/403 (DRF) ou redirige
 *   vers /accounts/login/ : dans les deux cas on renvoie l'utilisateur
 *   sur la page de login avec ?next= pour revenir ici après.
 */

export function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^|;\\s*)' + name + '=([^;]*)'))
  return match ? decodeURIComponent(match[2]) : null
}

let csrfReady = null

export function ensureCsrf() {
  if (!csrfReady) {
    csrfReady = fetch('/api/orthophotos/csrf/', { credentials: 'same-origin' })
      .catch(() => { csrfReady = null })
  }
  return csrfReady
}

function redirectToLogin() {
  const next = encodeURIComponent(window.location.pathname + window.location.hash)
  window.location.href = `/accounts/login/?next=${next}`
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

  // LoginRequiredMixin redirige vers la page HTML de login.
  if (response.redirected && response.url.includes('/accounts/login/')) {
    redirectToLogin()
    throw new ApiError('Session expirée', { status: 401 })
  }
  // 401 = pas authentifié → login. On NE redirige PAS sur 403 : DRF
  // renvoie 403 aussi bien pour une permission métier manquante que
  // pour une session expirée, et rediriger sur un refus de permission
  // créerait une boucle login → 403 → login. On remonte donc le 403
  // comme une erreur normale (message affiché en toast par l'appelant).
  if (response.status === 401) {
    redirectToLogin()
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
    redirectToLogin()
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
