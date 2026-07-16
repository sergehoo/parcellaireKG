import { AnimatePresence, motion } from 'framer-motion'

/**
 * Rail de contrôle flottant (verre dépoli), REPLIABLE pour ne pas masquer
 * la légende en permanence. Boutons groupés + micro-animations.
 */
const Icon = ({ d }) => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8}
    strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
)

const ICONS = {
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  reset: 'M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14.9-3M4 16a8 8 0 0014.9 3',
  locate: 'M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v3M12 19v3M2 12h3M19 12h3',
  target: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 8v0M12 12l0 0M9 12h6',
  full: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5',
  ruler: 'M3 17L17 3l4 4L7 21z M7 11l2 2M11 7l2 2M11 15l2 2',
  area: 'M4 4h16v16H4z M4 9h16M9 4v16',
  eraser: 'M7 21h10M5 13l6-6 8 8-6 6H9z',
  crosshair: 'M12 2v4M12 18v4M2 12h4M18 12h4M12 9a3 3 0 100 6 3 3 0 000-6z',
  share: 'M4 12v7a1 1 0 001 1h14a1 1 0 001-1v-7M16 6l-4-4-4 4M12 2v13',
  map: 'M9 4l6 2 6-2v14l-6 2-6-2-6 2V6z M9 4v14M15 6v14',
  print: 'M6 9V2h12v7M6 18H4a2 2 0 01-2-2v-3a2 2 0 012-2h16a2 2 0 012 2v3a2 2 0 01-2 2h-2M6 14h12v8H6z',
  chevron: 'M18 15l-6-6-6 6',
  tools: 'M14 7l-1.5-1.5a3.5 3.5 0 00-5 5L3 15v6h6l4.5-4.5a3.5 3.5 0 005-5L17 10',
}

function RailBtn({ title, icon, onClick, active, disabled }) {
  return (
    <motion.button
      type="button" title={title} onClick={onClick} disabled={disabled}
      whileHover={{ scale: disabled ? 1 : 1.12 }} whileTap={{ scale: disabled ? 1 : 0.9 }}
      className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${
        active ? 'bg-[var(--kaydan)] text-white'
          : disabled ? 'text-slate-300'
            : 'text-slate-700 hover:bg-white/70'
      }`}
    ><Icon d={ICONS[icon]} /></motion.button>
  )
}

const Sep = () => <div className="mx-auto my-1 h-px w-6 bg-slate-300/60" />

export default function ControlRail({
  api, measure, minimapOn, onMinimap, collapsed, onToggle,
  hasSelection, onRecenterSelection, cursorOn, onCursorToggle, onShare,
}) {
  if (!api) return null
  return (
    <div className="absolute left-3 top-1/2 z-[650] -translate-y-1/2">
      <AnimatePresence mode="wait">
        {collapsed ? (
          <motion.button
            key="closed" type="button" title="Outils de carte" onClick={() => onToggle(false)}
            initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }}
            whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.92 }}
            className="glass flex h-11 w-11 items-center justify-center rounded-2xl text-slate-700"
          ><Icon d={ICONS.tools} /></motion.button>
        ) : (
          <motion.div
            key="open"
            initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }}
            transition={{ type: 'spring', stiffness: 340, damping: 28 }}
            className="glass flex max-h-[80vh] flex-col gap-0.5 overflow-y-auto rounded-2xl p-1.5"
          >
            <motion.button
              type="button" title="Replier" onClick={() => onToggle(true)}
              whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
              className="mb-0.5 flex h-8 w-10 items-center justify-center rounded-xl text-slate-400 hover:bg-white/70 hover:text-slate-700"
            ><Icon d={ICONS.chevron} /></motion.button>

            <RailBtn title="Zoom avant" icon="plus" onClick={api.zoomIn} />
            <RailBtn title="Zoom arrière" icon="minus" onClick={api.zoomOut} />
            <Sep />
            <RailBtn title="Vue initiale" icon="reset" onClick={api.resetView} />
            <RailBtn title="Recentrer sur la sélection" icon="target" onClick={onRecenterSelection} disabled={!hasSelection} />
            <RailBtn title="Ma position" icon="locate" onClick={api.locate} />
            <RailBtn title="Plein écran" icon="full" onClick={api.fullscreen} />
            <Sep />
            <RailBtn title="Mesurer une distance" icon="ruler"
              active={measure?.active && measure.type === 'distance'} onClick={() => api.startMeasure('distance')} />
            <RailBtn title="Mesurer une surface" icon="area"
              active={measure?.active && measure.type === 'area'} onClick={() => api.startMeasure('area')} />
            <RailBtn title="Effacer les mesures" icon="eraser" onClick={api.clearMeasure} />
            <RailBtn title="Coordonnées du curseur" icon="crosshair" active={cursorOn} onClick={onCursorToggle} />
            <Sep />
            <RailBtn title="Mini-carte" icon="map" active={minimapOn} onClick={() => onMinimap(!minimapOn)} />
            <RailBtn title="Partager la vue (copier le lien)" icon="share" onClick={onShare} />
            <RailBtn title="Imprimer / PDF" icon="print" onClick={api.print} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
