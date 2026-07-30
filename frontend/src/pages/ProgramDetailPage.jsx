import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { deleteResource, getProgramSummary } from '../api/resources'
import { useCopilotContext } from '../copilot/pageContext'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toasts'
import { formatDate } from '../lib/format'

const card = 'rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800'

// Couleurs alignées sur la légende de la carte (Disponible / Réservé / Vendu / Litige).
const STATUS = {
  AVAILABLE: { label: 'Disponible', cell: 'bg-sky-100 text-sky-800 hover:bg-sky-200 dark:bg-sky-900/40 dark:text-sky-200', dot: 'bg-sky-500' },
  RESERVED: { label: 'Réservé', cell: 'bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-900/40 dark:text-amber-200', dot: 'bg-amber-500' },
  SOLD: { label: 'Vendu', cell: 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200', dot: 'bg-emerald-500' },
  OPTIONED: { label: 'En option', cell: 'bg-violet-100 text-violet-800 hover:bg-violet-200 dark:bg-violet-900/40 dark:text-violet-200', dot: 'bg-violet-500' },
  BLOCKED: { label: 'Bloqué', cell: 'bg-rose-100 text-rose-800 hover:bg-rose-200 dark:bg-rose-900/40 dark:text-rose-200', dot: 'bg-rose-500' },
  LITIGATION: { label: 'Litige', cell: 'bg-rose-100 text-rose-800 hover:bg-rose-200 dark:bg-rose-900/40 dark:text-rose-200', dot: 'bg-rose-500' },
  ARCHIVED: { label: 'Archivé', cell: 'bg-slate-100 text-slate-500 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-400', dot: 'bg-slate-400' },
}
const st = (k) => STATUS[k] || STATUS.AVAILABLE

function Kpi({ label, value, accent }) {
  return (
    <div className={`${card} px-4 py-3`}>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${accent || 'text-slate-900 dark:text-white'}`}>{value}</div>
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-50 px-4 py-2.5 last:border-0 dark:border-slate-700/50">
      <span className="text-sm text-slate-500 dark:text-slate-400">{label}</span>
      <span className="text-right text-sm font-medium text-slate-800 dark:text-slate-100">{value ?? '—'}</span>
    </div>
  )
}

export default function ProgramDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)

  useCopilotContext({ program_id: id })

  const load = useCallback(() => {
    const controller = new AbortController()
    getProgramSummary(id, { signal: controller.signal }).then(setData).catch((err) => {
      if (err.name !== 'AbortError') setError(err)
    })
    return () => controller.abort()
  }, [id])

  useEffect(() => load(), [load])

  const lots = data?.lots || []
  const visibleLots = useMemo(
    () => (filter ? lots.filter((l) => l.status === filter) : lots),
    [lots, filter],
  )

  async function onDelete() {
    setBusy(true)
    try {
      await deleteResource('programs', id)
      toast('Programme supprimé.', 'success')
      navigate('/r/programs')
    } catch (err) {
      toast(err.message || 'Suppression impossible.', 'error')
    } finally {
      setBusy(false)
      setConfirmDelete(false)
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <Link to="/r/programs" className="text-sm font-medium text-orange-600 hover:underline">← Programmes</Link>
        <p className="mt-4 text-sm text-red-600">Erreur : {error.message}</p>
      </div>
    )
  }
  if (!data) return <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-slate-400">Chargement…</div>

  const p = data.program || {}
  const s = data.stats || {}
  const byStatus = s.by_status || {}

  return (
    <div className="mx-auto max-w-6xl space-y-5 px-4 py-6">
      <div>
        <Link to="/r/programs" className="text-sm font-medium text-orange-600 hover:underline">← Programmes</Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{p.name || '—'}</h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {p.code} · {p.program_type_display || '—'} · {p.project_label || '—'}
            </p>
          </div>
          <div className="flex gap-2">
            <Link to={`/r/programs/${id}/edit`}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700">
              Modifier
            </Link>
            <button type="button" onClick={() => setConfirmDelete(true)}
              className="rounded-lg border border-red-300 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-950">
              Supprimer
            </button>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Kpi label="Lots" value={s.total_parcels ?? '—'} />
        <Kpi label="Commercialisés" value={`${s.commercialization_pct ?? 0}%`} accent="text-emerald-600 dark:text-emerald-400" />
        <Kpi label="Réservés" value={`${s.reservation_pct ?? 0}%`} accent="text-amber-600 dark:text-amber-400" />
        <Kpi label="CA (net)" value={s.ca_total ?? '—'} />
        <Kpi label="Encaissé" value={s.encaisse ?? '—'} accent="text-emerald-600 dark:text-emerald-400" />
      </div>

      {/* Caractéristiques */}
      <div className={card}>
        <div className="grid grid-cols-1 sm:grid-cols-2">
          <InfoRow label="Code" value={p.code} />
          <InfoRow label="Statut" value={p.status_display || p.status} />
          <InfoRow label="Type" value={p.program_type_display || p.program_type} />
          <InfoRow label="Surface totale" value={p.total_area_m2 ? `${Number(p.total_area_m2).toLocaleString('fr-FR')} m²` : '—'} />
          <InfoRow label="Lots estimés" value={p.estimated_lot_count} />
          <InfoRow label="Devise" value={p.currency} />
          <InfoRow label="Projet" value={p.project_label} />
          <InfoRow label="Pays" value={p.country_label} />
          <InfoRow label="Lots cartographiés" value={`${s.mapped_parcels ?? 0} / ${s.total_parcels ?? 0}`} />
          <InfoRow label="Orthophoto" value={s.has_orthophoto ? 'Disponible' : 'Aucune'} />
          <InfoRow label="Créé le" value={p.created_at ? formatDate(p.created_at) : '—'} />
        </div>
      </div>

      {/* Grille des lots */}
      <section className={`${card} overflow-hidden`}>
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-700">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-white">
            Lots <span className="text-slate-400">({visibleLots.length})</span>
          </h2>
          <div className="flex flex-wrap gap-1.5">
            <button type="button" onClick={() => setFilter('')}
              className={`rounded-full px-2.5 py-1 text-xs font-medium ${filter === '' ? 'bg-slate-800 text-white dark:bg-white dark:text-slate-900' : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'}`}>
              Tous {lots.length}
            </button>
            {Object.entries(byStatus).sort((a, b) => b[1] - a[1]).map(([key, n]) => (
              <button key={key} type="button" onClick={() => setFilter(filter === key ? '' : key)}
                className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${filter === key ? 'ring-2 ring-slate-400' : ''} ${st(key).cell}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${st(key).dot}`} />
                {st(key).label} {n}
              </button>
            ))}
          </div>
        </header>
        {visibleLots.length ? (
          <div className="grid gap-1.5 p-4"
            style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(3.75rem, 1fr))' }}>
            {visibleLots.map((l) => (
              <Link key={l.id} to={`/r/parcels/${l.id}`}
                title={`Lot ${l.lot} · ${st(l.status).label}${l.area ? ` · ${l.area} m²` : ''}${l.mapped ? ' · cartographié' : ''}`}
                className={`flex aspect-square flex-col items-center justify-center rounded-md text-xs font-semibold transition ${st(l.status).cell}`}>
                <span className="truncate px-1">{l.lot}</span>
              </Link>
            ))}
          </div>
        ) : (
          <p className="px-4 py-8 text-sm text-slate-400 dark:text-slate-500">Aucun lot pour ce filtre.</p>
        )}
      </section>

      <ConfirmDialog
        open={confirmDelete}
        title="Supprimer ce programme ?"
        message="Le programme sera désactivé. Ses lots et dossiers restent en base."
        confirmLabel={busy ? 'Suppression…' : 'Supprimer'}
        danger
        onConfirm={onDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}
