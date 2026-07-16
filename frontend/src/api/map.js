/**
 * API cartographie — consomme RealEstateMapAPIView (/api/map/assets/).
 *
 * La réponse contient :
 *  - assets[]        : parcelles + lots (GeoJSON, couleur/opacité par statut,
 *                      détails, métriques, timeline, images, stats masquées
 *                      par permission, orthophotos du programme…)
 *  - summaries[]     : cartouches (Actifs, Réservés/Vendus, CA potentiel)
 *  - filters[]       : Tous / Disponibles / Réservés / Vendus / En construction
 *  - tag_filters[]   : tags disponibles
 *  - user_rights     : {can_view_financial_data, can_view_patient_data, …}
 *  - orthophotos_by_program : {program_id: {current, all[]}}
 *  - counts, truncated, map_context
 *
 * Paramètres GET : program, project, status, tag, search, bbox, zoom, limit.
 */
import { request } from './client'

export function getMapAssets(params = {}, { signal } = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined),
  )
  const qs = query.toString()
  return request(`/api/map/assets/${qs ? `?${qs}` : ''}`, { signal })
}
