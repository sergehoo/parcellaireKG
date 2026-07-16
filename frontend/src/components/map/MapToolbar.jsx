import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

/**
 * Barre d'outils premium (verre dépoli) : marque KAYDAN + recherche
 * intelligente à suggestions instantanées + filtres. La recherche propose
 * des biens (par nom), programmes, projets et des commandes de statut
 * (« Disponibles », « Vendus »…) qui pilotent la carte.
 */
function BrandCard() {
  return (
    <div className="glass flex items-center gap-2.5 rounded-2xl px-3.5 py-2.5">
      <span className="flex h-10 w-10 items-center justify-center rounded-xl text-white" style={{ background: 'var(--kaydan)' }}>
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
          <path d="M3 21V7l6-3v3l6-3v4l6-2v15H3zm2-2h4v-3H5v3zm0-5h4v-3H5v3zm6 5h4v-3h-4v3zm0-5h4v-3h-4v3zm6 5h2v-3h-2v3z" />
        </svg>
      </span>
      <div className="leading-tight">
        <div className="text-sm font-extrabold tracking-wide text-slate-900">KAYDAN</div>
        <div className="text-[11px] text-slate-500">Parcellaire immobilier</div>
      </div>
    </div>
  )
}

export default function MapToolbar({
  refData, value, onChange, statusFilters, counts, truncated, buildSuggestions,
}) {
  const [q, setQ] = useState('')
  const [focus, setFocus] = useState(false)
  const boxRef = useRef(null)

  useEffect(() => {
    const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setFocus(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const programs = useMemo(() => {
    if (!refData) return []
    return value.project ? refData.programs.filter((p) => String(p.project_id) === String(value.project)) : refData.programs
  }, [refData, value.project])

  const suggestions = useMemo(() => (q.trim().length >= 2 ? buildSuggestions(q.trim()) : []), [q, buildSuggestions])

  function set(key, v) {
    const next = { ...value, [key]: v }
    if (key === 'project') next.program = ''
    onChange(next)
  }

  const ddl = 'glass rounded-xl px-3 py-2 text-sm font-semibold text-slate-700 focus:outline-none'

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 z-[660] flex flex-col gap-2 p-3">
      <div className="pointer-events-auto flex flex-wrap items-center gap-2">
        <BrandCard />

        <div ref={boxRef} className="relative">
          <div className="glass flex items-center rounded-xl">
            <svg className="ml-3 h-4 w-4 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.3-4.3M11 19a8 8 0 100-16 8 8 0 000 16z" />
            </svg>
            <input
              type="search" value={q} onFocus={() => setFocus(true)}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Rechercher lot, programme, client, statut…"
              className="w-80 rounded-xl bg-transparent py-2 pl-2 pr-3 text-sm text-slate-800 placeholder:text-slate-500 focus:outline-none"
            />
          </div>
          <AnimatePresence>
            {focus && suggestions.length > 0 && (
              <motion.ul
                initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
                className="glass absolute mt-1.5 max-h-80 w-96 overflow-auto rounded-2xl p-1.5"
              >
                {suggestions.map((s, i) => (
                  <li key={i}>
                    <button type="button"
                      onClick={() => { s.action(); setFocus(false); setQ('') }}
                      className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left hover:bg-white/70">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-xs"
                        style={{ background: s.color || '#e2571e22', color: s.color || '#e2571e' }}>{s.badge}</span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-slate-800">{s.label}</span>
                        {s.sub && <span className="block truncate text-xs text-slate-500">{s.sub}</span>}
                      </span>
                    </button>
                  </li>
                ))}
              </motion.ul>
            )}
          </AnimatePresence>
        </div>

        <select value={value.project || ''} onChange={(e) => set('project', e.target.value)} className={ddl}>
          <option value="">Tous les projets</option>
          {refData?.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={value.program || ''} onChange={(e) => set('program', e.target.value)} className={ddl}>
          <option value="">Tous les programmes</option>
          {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={value.status || ''} onChange={(e) => set('status', e.target.value)} className={ddl}>
          {(statusFilters || ['Tous']).map((s) => <option key={s} value={s === 'Tous' ? '' : s}>{s}</option>)}
        </select>
        {(value.project || value.program || value.status || value.search) && (
          <button type="button" onClick={() => onChange({ project: '', program: '', status: '', tag: '', search: '' })}
            className="glass rounded-xl px-3.5 py-2 text-sm font-semibold text-slate-600 hover:text-slate-900">
            Réinitialiser
          </button>
        )}
        {counts && (
          <span className="glass rounded-full px-3 py-1.5 text-xs font-medium text-slate-600">
            {counts.total_count} entité{counts.total_count > 1 ? 's' : ''}{truncated && <span className="ml-1 text-amber-600">· tronqué</span>}
          </span>
        )}
      </div>
    </div>
  )
}
