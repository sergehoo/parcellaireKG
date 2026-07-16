import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { BASEMAPS } from './MapCanvas'

/**
 * Sélecteur de vues premium (fond de carte + style de calque parcelles +
 * orthophoto). Bouton compact qui déploie un panneau verre dépoli animé.
 */
const LAYER_STYLES = [
  { key: 'polygones', label: 'Polygones' },
  { key: 'noms', label: 'Noms lots' },
  { key: 'reperes', label: 'Repères' },
  { key: 'none', label: 'Aucun' },
]

const BASE_SWATCH = {
  standard: 'linear-gradient(135deg,#dbe7d3,#cfe0f0)',
  clair: 'linear-gradient(135deg,#f8fafc,#e2e8f0)',
  sombre: 'linear-gradient(135deg,#1e293b,#0f172a)',
  satellite: 'linear-gradient(135deg,#3f6212,#1c3d0f)',
  relief: 'linear-gradient(135deg,#d9c7a3,#a3b18a)',
}

export default function ViewSelector({
  basemap, onBasemap, layerStyle, onLayerStyle,
  orthoActive, onOrthoToggle, canOrtho,
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="absolute bottom-3 right-3 z-[650] flex flex-col items-end gap-2">
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.96 }}
            transition={{ type: 'spring', stiffness: 320, damping: 26 }}
            className="glass w-64 rounded-2xl p-3"
          >
            <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--kaydan)' }}>
              Fond de carte
            </div>
            <div className="grid grid-cols-5 gap-1.5">
              {Object.entries(BASEMAPS).map(([key, def]) => (
                <button key={key} type="button" title={def.label} onClick={() => onBasemap(key)}
                  className={`flex flex-col items-center gap-1 rounded-lg p-1 transition ${basemap === key ? 'ring-2 ring-[var(--kaydan)]' : 'hover:bg-white/60'}`}>
                  <span className="h-8 w-8 rounded-md" style={{ background: BASE_SWATCH[key] }} />
                  <span className="text-[9px] text-slate-600">{def.label}</span>
                </button>
              ))}
            </div>

            <div className="mb-1.5 mt-3 text-[11px] font-bold uppercase tracking-wider" style={{ color: 'var(--kaydan)' }}>
              Calque parcelles
            </div>
            <div className="flex flex-wrap gap-1.5">
              {LAYER_STYLES.map((s) => (
                <button key={s.key} type="button" onClick={() => onLayerStyle(s.key)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${layerStyle === s.key ? 'bg-[var(--kaydan)] text-white' : 'bg-white/60 text-slate-700 hover:bg-white'}`}>
                  {s.label}
                </button>
              ))}
            </div>

            <button type="button" disabled={!canOrtho} onClick={onOrthoToggle}
              className={`mt-3 flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition ${
                orthoActive ? 'bg-[var(--kaydan)] text-white' : 'bg-white/60 text-slate-700 hover:bg-white disabled:opacity-40'
              }`}>
              Orthophoto
              <span className={`h-4 w-7 rounded-full p-0.5 transition ${orthoActive ? 'bg-white/40' : 'bg-slate-300'}`}>
                <span className={`block h-3 w-3 rounded-full bg-white transition-transform ${orthoActive ? 'translate-x-3' : ''}`} />
              </span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        type="button" whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
        onClick={() => setOpen((o) => !o)}
        className="glass flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold text-slate-800"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2l9 4.5-9 4.5-9-4.5L12 2zM3 12l9 4.5 9-4.5M3 17l9 4.5 9-4.5" />
        </svg>
        Vues
      </motion.button>
    </div>
  )
}
