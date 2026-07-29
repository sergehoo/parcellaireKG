// Bus léger pour piloter la carte depuis le Copilot. `requestMapFocus` gère la
// course « naviguer vers /carte puis centrer » : la cible est mémorisée et
// consommée quand MapView est prêt (api Leaflet disponible), en plus de
// l'événement live pour quand on est déjà sur la carte.
let pending = null

export function requestMapFocus(focus) {
  pending = focus
  window.dispatchEvent(new CustomEvent('kg-copilot-map-focus', { detail: focus }))
}

export function takePendingMapFocus() {
  const f = pending
  pending = null
  return f
}
