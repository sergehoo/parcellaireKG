import { motion } from 'framer-motion'

/**
 * Rail de contrôle flottant (verre dépoli). Chaque bouton anime au survol
 * et au tap. Les actions sont fournies par l'API impérative de MapCanvas.
 */
const Icon = ({ d, path }) => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8}
    strokeLinecap="round" strokeLinejoin="round">
    {path || <path d={d} />}
  </svg>
)

const ICONS = {
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  reset: 'M4 4v6h6M20 20v-6h-6M20 8a8 8 0 00-14.9-3M4 16a8 8 0 0014.9 3',
  locate: 'M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v3M12 19v3M2 12h3M19 12h3',
  full: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5',
  ruler: 'M3 17L17 3l4 4L7 21z M7 11l2 2M11 7l2 2M11 15l2 2',
  area: 'M4 4h16v16H4z M4 9h16M9 4v16',
  eraser: 'M7 21h10M5 13l6-6 8 8-6 6H9z',
  print: 'M6 9V2h12v7M6 18H4a2 2 0 01-2-2v-3a2 2 0 012-2h16a2 2 0 012 2v3a2 2 0 01-2 2h-2M6 14h12v8H6z',
  map: 'M9 4l6 2 6-2v14l-6 2-6-2-6 2V6z M9 4v14M15 6v14',
}

function RailButton({ title, icon, onClick, active }) {
  return (
    <motion.button
      type="button" title={title} onClick={onClick}
      whileHover={{ scale: 1.12 }} whileTap={{ scale: 0.9 }}
      className={`flex h-10 w-10 items-center justify-center rounded-xl transition-colors ${
        active ? 'bg-[var(--kaydan)] text-white' : 'text-slate-700 hover:bg-white/70'
      }`}
    >
      <Icon d={ICONS[icon]} />
    </motion.button>
  )
}

export default function ControlRail({ api, measure, minimapOn, onMinimap }) {
  if (!api) return null
  const Sep = () => <div className="my-1 h-px w-6 self-center bg-slate-300/60" />
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.35 }}
      className="glass absolute right-3 top-1/2 z-[650] flex -translate-y-1/2 flex-col gap-0.5 rounded-2xl p-1.5"
    >
      <RailButton title="Zoom avant" icon="plus" onClick={api.zoomIn} />
      <RailButton title="Zoom arrière" icon="minus" onClick={api.zoomOut} />
      <Sep />
      <RailButton title="Vue initiale" icon="reset" onClick={api.resetView} />
      <RailButton title="Ma position" icon="locate" onClick={api.locate} />
      <RailButton title="Plein écran" icon="full" onClick={api.fullscreen} />
      <Sep />
      <RailButton title="Mesurer une distance" icon="ruler"
        active={measure?.active && measure.type === 'distance'} onClick={() => api.startMeasure('distance')} />
      <RailButton title="Mesurer une surface" icon="area"
        active={measure?.active && measure.type === 'area'} onClick={() => api.startMeasure('area')} />
      <RailButton title="Effacer les mesures" icon="eraser" onClick={api.clearMeasure} />
      <Sep />
      <RailButton title="Mini-carte" icon="map" active={minimapOn} onClick={() => onMinimap(!minimapOn)} />
      <RailButton title="Imprimer / PDF" icon="print" onClick={api.print} />
    </motion.div>
  )
}
