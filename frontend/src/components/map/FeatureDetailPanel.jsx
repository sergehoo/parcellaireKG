import { useNavigate } from 'react-router-dom'
import { LEVELS } from '../../lib/criticality'

/**
 * Panneau latéral « ACTIF SÉLECTIONNÉ » façon KAYDAN. Affiche les données
 * renvoyées par l'API (déjà masquées par permission côté serveur).
 *
 * « Ouvrir la fiche complète » : les parcelles ouvrent la fiche interne du
 * SPA (`#/r/parcels/:id`) — cohérent et fonctionnel en dev comme en prod
 * (le lien Django absolu `/parcels/:id/` n'existe pas sous le serveur Vite).
 * Les lots (PropertyAsset), non encore portés dans le SPA, pointent vers la
 * page Django `/assets/:id/`.
 *
 * Rappels : on n'utilise PAS les classes Tailwind `statusBadge`/`priority_badge`
 * de l'API (purgées au build) ; on s'appuie sur les couleurs (`color`,
 * `priority_stats.priority_color`) en style inline.
 */
function detailTarget(feat) {
  if (!feat?.id) return null
  if (feat.entity_type === 'PARCEL') return { spa: `/r/parcels/${feat.id}` }
  if (feat.entity_type === 'PROPERTY_ASSET') return { href: `/assets/${feat.id}/` }
  return null
}

function Chip({ children, color, bg }) {
  return (
    <span
      className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
      style={{ color: color || '#0369a1', background: bg || '#e0f2fe' }}
    >
      {children}
    </span>
  )
}

export default function FeatureDetailPanel({ feature, alert = null, onClose }) {
  const navigate = useNavigate()
  if (!feature) return null
  const f = feature
  const target = detailTarget(f)
  const alertStyle = alert ? (LEVELS[alert.level] || LEVELS.CRITIQUE) : null
  const cs = f.construction_stats || {}
  const fs = f.financial_stats || {}
  const ps = f.priority_stats || {}
  const units = f.unit_summary || {}
  const showUnits = f.is_multi_unit && (units.total_units || 0) > 0

  const summaryBits = [
    cs.taux_avancement && cs.taux_avancement !== 'Masqué' ? `Avancement : ${cs.taux_avancement}` : null,
    fs.taux_paiement && fs.taux_paiement !== 'Masqué' ? `Paiement : ${fs.taux_paiement}` : null,
    cs.valeur_hypothecaire && cs.valeur_hypothecaire !== 'Masqué' ? `Valeur hyp. : ${cs.valeur_hypothecaire}` : null,
  ].filter(Boolean)

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="relative border-b border-slate-100 p-4 pr-12">
        <div className="text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--kaydan)' }}>
          Actif sélectionné
        </div>
        <h2 className="mt-1 text-xl font-extrabold text-slate-900">{f.name || '—'}</h2>
        <p className="truncate text-sm text-slate-500">{f.program || '—'}</p>

        <div className="mt-2.5 flex flex-wrap gap-1.5">
          <Chip color="#fff" bg={f.color || '#38bdf8'}>{f.status || '—'}</Chip>
          {f.entity_type === 'PARCEL' && <Chip color="#475569" bg="#f1f5f9">Parcelle CRM</Chip>}
          {ps.priority_label && (
            <Chip color="#fff" bg={ps.priority_color || '#22c55e'}>{ps.priority_label}</Chip>
          )}
        </div>

        {summaryBits.length > 0 && (
          <p className="mt-2.5 text-xs text-slate-500">{summaryBits.join(' • ')}</p>
        )}

        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-500 hover:bg-slate-200"
          aria-label="Fermer"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        {alert && alertStyle && f.parcel_id != null && (
          <button
            type="button"
            onClick={() => navigate(`/notifications?parcel=${f.parcel_id}`)}
            className={`flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-left ${alertStyle.bg}`}
          >
            <span className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: alertStyle.dot }} />
              <span className={`text-sm font-semibold ${alertStyle.text}`}>
                {alert.count} alerte(s) — {alertStyle.label}
              </span>
            </span>
            <span className={`text-xs font-medium ${alertStyle.text}`}>Voir →</span>
          </button>
        )}

        {showUnits && (
          <div className="grid grid-cols-2 gap-2 text-sm">
            {[['Total', units.total_units], ['Disponibles', units.available_units],
              ['Réservées', units.reserved_units], ['Vendues', units.sold_units]].map(([l, v]) => (
              <div key={l} className="flex justify-between rounded-lg bg-slate-50 px-2.5 py-1.5">
                <span className="text-slate-500">{l}</span>
                <span className="font-semibold text-slate-800">{v ?? 0}</span>
              </div>
            ))}
          </div>
        )}

        {f.details?.length > 0 && (
          <dl className="overflow-hidden rounded-xl border border-slate-100">
            {f.details.map((d, i) => (
              <div key={i} className={`flex items-center justify-between gap-3 px-3 py-2.5 text-sm ${i % 2 ? 'bg-white' : 'bg-slate-50/60'}`}>
                <dt className="text-slate-500">{d.label}</dt>
                <dd className="text-right font-semibold text-slate-800">{d.value}</dd>
              </div>
            ))}
          </dl>
        )}

        {f.metrics?.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {f.metrics.map((m, i) => (
              <span key={i} className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs text-slate-700">
                {m.label} : <span className="font-semibold">{m.value}</span>
              </span>
            ))}
          </div>
        )}

        {f.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {f.tags.map((t, i) => (
              <span key={i} className="rounded-full px-2 py-0.5 text-xs ring-1 ring-inset"
                style={{ color: t.color || '#0369a1', borderColor: t.color || '#bae6fd' }}>
                {t.name || t.label || String(t)}
              </span>
            ))}
          </div>
        )}

        {f.images?.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            {f.images.map((src, i) => (
              <a key={i} href={src} target="_blank" rel="noreferrer">
                <img src={src} alt="" className="h-20 w-full rounded-lg object-cover" loading="lazy" />
              </a>
            ))}
          </div>
        )}

        {f.timeline?.length > 0 && (
          <section>
            <h3 className="mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
              Timeline commerciale
            </h3>
            <ol className="space-y-3">
              {f.timeline.map((t, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: 'var(--kaydan)' }} />
                  <div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-semibold text-slate-800">{t.label}</span>
                      <span className="text-xs text-slate-400">{t.date}</span>
                    </div>
                    {t.text && <p className="text-sm text-slate-600">{t.text}</p>}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>

      {target && (
        <div className="border-t border-slate-100 p-4">
          {target.spa ? (
            <button
              type="button"
              onClick={() => navigate(target.spa)}
              className="block w-full rounded-xl px-4 py-2.5 text-center text-sm font-semibold text-white"
              style={{ background: 'var(--kaydan)' }}
            >
              Ouvrir la fiche complète
            </button>
          ) : (
            <a
              href={target.href}
              className="block w-full rounded-xl px-4 py-2.5 text-center text-sm font-semibold text-white"
              style={{ background: 'var(--kaydan)' }}
            >
              Ouvrir la fiche complète
            </a>
          )}
        </div>
      )}
    </div>
  )
}
