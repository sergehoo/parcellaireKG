import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboard } from '../api/resources'
import { badgeClass } from '../lib/badges'
import { formatDate } from '../lib/format'

const KPIS = [
  { key: 'projects', label: 'Projets', to: '/r/projects' },
  { key: 'programs', label: 'Programmes', to: '/r/programs' },
  { key: 'parcels', label: 'Parcelles', to: '/r/parcels' },
  { key: 'customers', label: 'Clients', to: '/r/customers' },
  { key: 'sales', label: 'Ventes', to: '/r/sales' },
  { key: 'reservations', label: 'Réservations', to: '/r/reservations' },
]

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    getDashboard().then(setData).catch(setError)
  }, [])

  if (error) return <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-6 text-rose-700">{error.message}</div>
  if (!data) return <div className="py-20 text-center text-slate-500">Chargement…</div>

  const maxStatus = Math.max(1, ...data.parcels_by_status.map((s) => s.count))

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Tableau de bord</h1>
      <p className="mb-6 text-sm text-slate-500">Vue d'ensemble du portefeuille parcellaire &amp; commercial.</p>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {KPIS.map((k) => (
          <Link key={k.key} to={k.to}
            className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-orange-300 hover:shadow">
            <div className="text-2xl font-extrabold text-slate-900">{data.counts[k.key] ?? '—'}</div>
            <div className="text-xs uppercase tracking-wide text-slate-500">{k.label}</div>
          </Link>
        ))}
      </div>

      {/* Finance */}
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-xl p-5 text-white shadow-sm" style={{ background: 'var(--kaydan)' }}>
          <div className="text-xs uppercase tracking-wide opacity-80">Chiffre d'affaires (ventes)</div>
          <div className="mt-1 text-2xl font-extrabold">{data.finance.ca_total}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs uppercase tracking-wide text-slate-500">Encaissements confirmés</div>
          <div className="mt-1 text-2xl font-extrabold text-slate-900">{data.finance.paid_total}</div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Répartition parcelles */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 font-semibold text-slate-900">Parcelles par statut</h2>
          <div className="space-y-2">
            {data.parcels_by_status.map((s) => (
              <div key={s.status}>
                <div className="mb-0.5 flex justify-between text-sm">
                  <span className="text-slate-600">{s.status}</span>
                  <span className="font-medium text-slate-800">{s.count}</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full" style={{ width: `${(s.count / maxStatus) * 100}%`, background: 'var(--kaydan)' }} />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Ventes récentes */}
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Ventes récentes</h2>
            <Link to="/r/sales" className="text-sm font-medium text-orange-600 hover:underline">Tout voir →</Link>
          </div>
          <div className="divide-y divide-slate-100">
            {data.recent_sales.length === 0 && <p className="py-6 text-center text-sm text-slate-500">Aucune vente.</p>}
            {data.recent_sales.map((s) => (
              <Link key={s.id} to={`/r/sales/${s.id}`} className="flex items-center justify-between gap-2 py-2.5 hover:bg-slate-50">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-slate-800">{s.customer}</div>
                  <div className="truncate text-xs text-slate-500">{s.program} · {formatDate(s.sale_date)}</div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className="text-sm font-semibold text-slate-800">{s.net_price}</span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badgeClass(s.status)}`}>{s.status}</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
