/**
 * Panneau latéral de détail d'une feature sélectionnée sur la carte.
 * Affiche ce que renvoie l'API (détails, métriques, unités, timeline,
 * images, tags), avec masquage déjà appliqué côté serveur selon les
 * permissions. Le CRUD reste sur Django : « Ouvrir la fiche » pointe
 * vers la page Django de l'entité.
 *
 * Note : on n'utilise PAS les classes Tailwind `statusBadge` renvoyées
 * par l'API (elles seraient purgées du bundle, non vues au build) ; on
 * s'appuie sur `color` en style inline.
 */
function detailHref(feat) {
  if (!feat?.id) return null
  if (feat.entity_type === 'PARCEL') return `/parcels/${feat.id}/`
  if (feat.entity_type === 'PROPERTY_ASSET') return `/assets/${feat.id}/`
  return null
}

export default function FeatureDetailPanel({ feature, onClose }) {
  if (!feature) return null
  const f = feature
  const href = detailHref(f)
  const units = f.unit_summary || {}
  const showUnits = f.is_multi_unit && (units.total_units || 0) > 0

  return (
    <div className="flex h-full flex-col bg-white">
      {/* En-tête */}
      <div className="flex items-start justify-between gap-2 border-b border-slate-200 p-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: f.color || '#38bdf8' }} />
            <h2 className="truncate text-lg font-semibold text-slate-900">{f.name || '—'}</h2>
          </div>
          <p className="mt-0.5 truncate text-sm text-slate-500">
            {f.project && f.project !== '—' ? `${f.project} · ` : ''}{f.program || '—'}
          </p>
          <p className="mt-1 text-sm font-medium" style={{ color: f.color || '#0f172a' }}>{f.status || ''}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          aria-label="Fermer"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4">
        {/* Chiffres clés */}
        <div className="grid grid-cols-3 gap-2">
          <KeyStat label="Surface" value={f.surface} />
          <KeyStat label="Prix" value={f.price} />
          <KeyStat label="Paiement" value={f.payment} />
        </div>

        {/* Unités (bâtiments multi-lots) */}
        {showUnits && (
          <Section title="Unités">
            <div className="grid grid-cols-2 gap-2 text-sm">
              <UnitRow label="Total" value={units.total_units} />
              <UnitRow label="Disponibles" value={units.available_units} />
              <UnitRow label="Réservées" value={units.reserved_units} />
              <UnitRow label="Vendues" value={units.sold_units} />
            </div>
          </Section>
        )}

        {/* Détails */}
        {f.details?.length > 0 && (
          <Section title="Détails">
            <dl className="space-y-1.5 text-sm">
              {f.details.map((d, i) => (
                <div key={i} className="flex justify-between gap-3">
                  <dt className="text-slate-500">{d.label}</dt>
                  <dd className="text-right font-medium text-slate-800">{d.value}</dd>
                </div>
              ))}
            </dl>
          </Section>
        )}

        {/* Métriques */}
        {f.metrics?.length > 0 && (
          <Section title="Métriques">
            <div className="flex flex-wrap gap-2">
              {f.metrics.map((m, i) => (
                <span key={i} className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs text-slate-700">
                  {m.label} : <span className="font-medium">{m.value}</span>
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Tags */}
        {f.tags?.length > 0 && (
          <Section title="Tags">
            <div className="flex flex-wrap gap-1.5">
              {f.tags.map((t, i) => (
                <span
                  key={i}
                  className="rounded-full px-2 py-0.5 text-xs ring-1 ring-inset"
                  style={{ color: t.color || '#0369a1', borderColor: t.color || '#bae6fd' }}
                >
                  {t.name || t.label || String(t)}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Images */}
        {f.images?.length > 0 && (
          <Section title="Photos">
            <div className="grid grid-cols-3 gap-2">
              {f.images.map((src, i) => (
                <a key={i} href={src} target="_blank" rel="noreferrer" className="block">
                  <img src={src} alt="" className="h-20 w-full rounded-lg object-cover" loading="lazy" />
                </a>
              ))}
            </div>
          </Section>
        )}

        {/* Timeline */}
        {f.timeline?.length > 0 && (
          <Section title="Historique">
            <ol className="space-y-3">
              {f.timeline.map((t, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-slate-300" />
                  <div>
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-medium text-slate-800">{t.label}</span>
                      <span className="text-xs text-slate-400">{t.date}</span>
                    </div>
                    {t.text && <p className="text-sm text-slate-600">{t.text}</p>}
                  </div>
                </li>
              ))}
            </ol>
          </Section>
        )}
      </div>

      {/* Pied : lien vers la fiche Django */}
      {href && (
        <div className="border-t border-slate-200 p-4">
          <a
            href={href}
            className="block w-full rounded-lg bg-sky-600 px-4 py-2 text-center text-sm font-medium text-white hover:bg-sky-700"
          >
            Ouvrir la fiche complète
          </a>
        </div>
      )}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h3>
      {children}
    </section>
  )
}

function KeyStat({ label, value }) {
  return (
    <div className="rounded-lg bg-slate-50 p-2 text-center">
      <div className="truncate text-sm font-semibold text-slate-900">{value || '—'}</div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  )
}

function UnitRow({ label, value }) {
  return (
    <div className="flex justify-between rounded bg-slate-50 px-2 py-1">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-800">{value ?? 0}</span>
    </div>
  )
}
