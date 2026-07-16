/**
 * Légende des statuts + cartouches de synthèse (Actifs, Réservés/Vendus,
 * CA potentiel — ce dernier masqué si l'utilisateur n'a pas le droit
 * financier). Les couleurs reprennent celles renvoyées par l'API.
 */
const LEGEND = [
  { label: 'Disponible', color: '#38bdf8' },
  { label: 'Réservé', color: '#f59e0b' },
  { label: 'Vendu', color: '#10b981' },
  { label: 'Bloqué / litige', color: '#f43f5e' },
  { label: 'Archivé', color: '#94a3b8' },
]

export default function MapLegend({ summaries = [] }) {
  return (
    <div className="pointer-events-auto rounded-xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
      {summaries.length > 0 && (
        <div className="mb-3 grid grid-cols-3 gap-2">
          {summaries.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-sm font-semibold text-slate-900">{s.value}</div>
              <div className="text-[10px] uppercase tracking-wide text-slate-500">{s.label}</div>
            </div>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {LEGEND.map((item) => (
          <span key={item.label} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: item.color }} />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  )
}
