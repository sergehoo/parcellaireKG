import { useEffect, useMemo, useRef, useState } from 'react'

/**
 * Barre de filtres de la carte : projet, programme (dépendant du projet),
 * statut, tag, recherche texte (debounced). `filters` et `tagFilters`
 * viennent de la réponse de l'API map ; projets/programmes de reference-data.
 */
export default function MapFilters({
  refData,
  statusFilters = [],
  tagFilters = [],
  value,
  onChange,
  counts,
  truncated,
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

  const sel = 'rounded-lg border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-700 shadow-sm focus:border-sky-500 focus:ring-sky-500'
  const hasActive = value.project || value.program || value.status || value.tag || value.search

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="search"
        value={searchInput}
        onChange={(e) => onSearch(e.target.value)}
        placeholder="Rechercher lot, client…"
        className="w-48 rounded-lg border-slate-300 px-3 py-1.5 text-sm shadow-sm focus:border-sky-500 focus:ring-sky-500"
      />
      <select value={value.project || ''} onChange={(e) => set('project', e.target.value)} className={sel}>
        <option value="">Tous les projets</option>
        {refData?.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <select value={value.program || ''} onChange={(e) => set('program', e.target.value)} className={sel}>
        <option value="">Tous les programmes</option>
        {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
      <select value={value.status || ''} onChange={(e) => set('status', e.target.value)} className={sel}>
        {statusFilters.map((s) => (
          <option key={s} value={s === 'Tous' ? '' : s}>{s}</option>
        ))}
      </select>
      {tagFilters.length > 0 && (
        <select value={value.tag || ''} onChange={(e) => set('tag', e.target.value)} className={sel}>
          <option value="">Tous les tags</option>
          {tagFilters.map((t) => (
            <option key={t.id ?? t.name} value={t.name}>{t.name}{t.count != null ? ` (${t.count})` : ''}</option>
          ))}
        </select>
      )}
      {hasActive && (
        <button
          type="button"
          onClick={() => onChange({ project: '', program: '', status: '', tag: '', search: '' })}
          className="text-sm text-sky-600 hover:underline"
        >
          Réinitialiser
        </button>
      )}
      <span className="ml-auto text-xs text-slate-500">
        {counts ? `${counts.total_count} entité${counts.total_count > 1 ? 's' : ''}` : ''}
        {truncated && <span className="ml-1 text-amber-600">(tronqué)</span>}
      </span>
    </div>
  )
}
