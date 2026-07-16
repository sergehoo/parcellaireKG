import { motion } from 'framer-motion'

/**
 * Légende + synthèse (verre dépoli). Coloration priorité travaux en mode
 * « Noms lots », statut commercial sinon.
 */
const PRIORITY = [
  { label: 'Faible', color: '#22c55e' },
  { label: 'Moyenne', color: '#f59e0b' },
  { label: 'Élevée', color: '#ef4444' },
]
const STATUS = [
  { label: 'Disponible', color: '#38bdf8' },
  { label: 'Réservé', color: '#f59e0b' },
  { label: 'Vendu', color: '#10b981' },
  { label: 'Bloqué / litige', color: '#f43f5e' },
]

export default function MapLegend({ summaries = [], variant = 'status' }) {
  const priority = variant === 'priority'
  const items = priority ? PRIORITY : STATUS
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}
      className="glass w-64 rounded-2xl p-3.5"
    >
      {summaries.length > 0 && (
        <div className="mb-3 grid grid-cols-3 gap-2 border-b border-slate-200/60 pb-3">
          {summaries.map((s) => (
            <div key={s.label} className="text-center">
              <div className="text-sm font-bold text-slate-900">{s.value}</div>
              <div className="text-[9px] uppercase leading-tight tracking-wide text-slate-500">{s.label}</div>
            </div>
          ))}
        </div>
      )}
      <div className="mb-2 text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--kaydan)' }}>
        {priority ? 'Priorité travaux' : 'Statut commercial'}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1.5">
        {items.map((item) => (
          <span key={item.label} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
            {item.label}
          </span>
        ))}
      </div>
      {priority && (
        <div className="mt-2.5 border-t border-slate-200/60 pt-2 text-[10px] text-slate-400">
          T = Travaux · P = Paiement · V = Variation
        </div>
      )}
    </motion.div>
  )
}
