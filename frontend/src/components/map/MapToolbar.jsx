import { useEffect, useMemo, useRef, useState } from 'react'

/**
 * Barre d'outils flottante de la carte, façon KAYDAN :
 * carte de marque + recherche + sélecteurs projet/programme + pills de
 * mode d'affichage (Parcelles / Noms lots / OSM / Orthophoto / Mixte).
 */
const MODES = [
  { key: 'parcelles', label: 'Parcelles' },
  { key: 'noms', label: 'Noms lots' },
  { key: 'osm', label: 'OSM' },
  { key: 'orthophoto', label: 'Orthophoto' },
  { key: 'mixte', label: 'Mixte' },
]

function BrandCard() {
  return (
    <div className="flex items-center gap-2.5 rounded-2xl bg-white/95 px-3.5 py-2.5 shadow-lg backdrop-blur">
      <span
        className="flex h-10 w-10 items-center justify-center rounded-xl text-white"
        style={{ background: 'var(--kaydan)' }}
      >
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
  refData, value, onChange, mode, onMode, counts, truncated, statusFilters,
}) {
  const [searchInput, setSearchInput] = useState(value.search || '')
  const searchTimer = useRef(null)
  useEffect(() => { setSearchInput(value.search || '') }, [value.search])

  const programs = useMemo(() => {
    if (!refData) return []
    return value.project
      ? refData.programs.filter((p) => String(p.project_id) === String(value.project))
      : refData.programs
  }, [refData, value.project])

  function set(key, v) {
    const next = { ...value, [key]: v }
    if (key === 'project') next.program = ''
    onChange(next)
  }
  function onSearch(v) {
    setSearchInput(v)
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => set('search', v.trim()), 400)
  }

  const ddl = 'rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm focus:border-orange-400 focus:ring-orange-400'

  return (
    <div className="pointer-events-none absolute inset-x-0 top-0 z-[600] flex flex-col gap-2 p-3">
      <div className="pointer-events-auto flex flex-wrap items-center gap-2">
        <BrandCard />

        <div className="relative">
          <svg className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.3-4.3M11 19a8 8 0 100-16 8 8 0 000 16z" />
          </svg>
          <input
            type="search"
            value={searchInput}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Rechercher projet, programme, lot…"
            className="w-72 rounded-xl border border-slate-200 bg-white/95 py-2 pl-9 pr-3 text-sm shadow-lg backdrop-blur focus:border-orange-400 focus:ring-orange-400"
          />
        </div>

        <select value={value.project || ''} onChange={(e) => set('project', e.target.value)} className={`${ddl} shadow-lg`}>
          <option value="">Tous les projets</option>
          {refData?.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select value={value.program || ''} onChange={(e) => set('program', e.target.value)} className={`${ddl} shadow-lg`}>
          <option value="">Tous les programmes</option>
          {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      {/* Pills de mode + statut + réinitialiser */}
      <div className="pointer-events-auto flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 rounded-full bg-slate-900/90 p-1 shadow-lg backdrop-blur">
          {MODES.map((m) => (
            <button
              key={m.key}
              type="button"
              onClick={() => onMode(m.key)}
              className={`rounded-full px-3.5 py-1.5 text-sm font-semibold transition ${
                mode === m.key ? 'bg-white text-slate-900' : 'text-slate-200 hover:text-white'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        <select
          value={value.status || ''}
          onChange={(e) => set('status', e.target.value)}
          className="rounded-full border border-slate-200 bg-white/95 px-3 py-1.5 text-sm font-semibold text-slate-700 shadow-lg backdrop-blur focus:border-orange-400 focus:ring-orange-400"
        >
          {(statusFilters || ['Tous']).map((s) => (
            <option key={s} value={s === 'Tous' ? '' : s}>{s}</option>
          ))}
        </select>

        {(value.project || value.program || value.status || value.search) && (
          <button
            type="button"
            onClick={() => onChange({ project: '', program: '', status: '', tag: '', search: '' })}
            className="rounded-full bg-white/95 px-3.5 py-1.5 text-sm font-semibold text-slate-600 shadow-lg backdrop-blur hover:text-slate-900"
          >
            Réinitialiser
          </button>
        )}

        {counts && (
          <span className="rounded-full bg-white/95 px-3 py-1.5 text-xs font-medium text-slate-500 shadow-lg backdrop-blur">
            {counts.total_count} entité{counts.total_count > 1 ? 's' : ''}
            {truncated && <span className="ml-1 text-amber-600">· tronqué</span>}
          </span>
        )}
      </div>
    </div>
  )
}
