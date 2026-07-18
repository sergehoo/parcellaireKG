import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { exportDashboardReport, getAnalyticsDashboard } from '../api/analytics'
import { useToast } from '../components/Toasts'
import { levelStyle, bandStyle } from '../lib/criticality'

const KPI_TILES = [
  { key: 'projects', label: 'Projets', to: '/r/projects' },
  { key: 'programs', label: 'Programmes', to: '/r/programs' },
  { key: 'parcels', label: 'Parcelles', to: '/r/parcels' },
  { key: 'customers', label: 'Clients', to: '/r/customers' },
  { key: 'sales', label: 'Ventes', to: '/r/sales' },
  { key: 'reservations', label: 'Réservations', to: '/r/reservations' },
]

function Metric({ label, value, sub, accent }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-xl font-extrabold ${accent || 'text-slate-900'}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-400">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    getAnalyticsDashboard().then(setData).catch(setError)
  }, [])

  async function doExportPdf() {
    setExporting(true)
    try {
      await exportDashboardReport()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setExporting(false)
    }
  }

  if (error) return <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-6 text-rose-700">{error.message}</div>
  if (!data) return <div className="py-20 text-center text-slate-500">Analyse en cours…</div>

  const k = data.kpis

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Centre de pilotage</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Vision décisionnelle temps réel — indicateurs, santé des programmes, alertes et clients à risque.
          </p>
        </div>
        <button type="button" onClick={doExportPdf} disabled={exporting}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50">
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="9" y1="15" x2="15" y2="15" />
          </svg>
          {exporting ? 'Génération…' : 'Rapport PDF'}
        </button>
      </div>

      {/* Compteurs rapides */}
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        {KPI_TILES.map((t) => (
          <Link key={t.key} to={t.to}
            className="rounded-xl border border-slate-200 bg-white p-3 text-center shadow-sm transition hover:border-orange-300 hover:shadow">
            <div className="text-xl font-extrabold text-slate-900">{data.counts[t.key] ?? '—'}</div>
            <div className="text-[10px] uppercase tracking-wide text-slate-500">{t.label}</div>
          </Link>
        ))}
      </div>

      {/* KPIs stratégiques */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric label="Chiffre d'affaires" value={k.ca_potentiel} />
        <Metric label="Encaissé" value={k.encaisse} sub={`Taux d'encaissement ${k.taux_encaissement} %`} accent="text-emerald-700" />
        <Metric label="Reste à encaisser" value={k.reste_a_encaisser} accent="text-orange-700" />
        <Metric label="Valeur hypothécaire" value={k.valeur_hypothecaire} sub={`Couverture ${k.couverture_hypothecaire} %`} />
        <Metric label="Avancement construction" value={`${k.avancement_construction_moyen} %`} />
        <Metric label="Commercialisation" value={`${k.taux_commercialisation} %`} sub={`Réservation ${k.taux_reservation} %`} />
        <Metric label="IDCP moyen" value={`${k.idcp_moyen > 0 ? '+' : ''}${k.idcp_moyen} %`}
          sub="Paiement − construction" accent={k.idcp_moyen > 15 ? 'text-rose-700' : 'text-slate-900'} />
        <Metric label="Clients à risque" value={`${k.clients_critiques + k.clients_eleves}`}
          sub={`${k.clients_critiques} critiques · ${k.clients_eleves} élevés`} accent="text-rose-700" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Alertes métier */}
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-1">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-slate-900">Alertes métier</h2>
            <Link to="/notifications" className="text-sm font-medium text-orange-600 hover:underline">Centre →</Link>
          </div>
          <div className="space-y-2">
            {data.alerts.length === 0 && <p className="py-6 text-center text-sm text-slate-500">Aucune alerte.</p>}
            {data.alerts.map((a, i) => {
              const s = levelStyle(a.level)
              return (
                <motion.div key={a.key} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}
                  className="flex items-start gap-2.5 rounded-xl border border-slate-100 p-2.5">
                  <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.dot }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-slate-800">{a.label}</span>
                      <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-bold ${s.bg} ${s.text}`}>{a.count}</span>
                    </div>
                    <p className="text-xs text-slate-500">{a.detail}</p>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </section>

        {/* Santé des programmes */}
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h2 className="mb-3 font-semibold text-slate-900">Score de santé des programmes</h2>
          <div className="space-y-3">
            {data.programs_health.map((p) => {
              const b = bandStyle(p.band)
              return (
                <Link key={p.id} to={`/carte?program=${p.id}`}
                  className="block rounded-xl border border-slate-100 p-3 transition hover:border-orange-200 hover:bg-orange-50/30">
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-slate-800">{p.name}</div>
                      <div className="truncate text-xs text-slate-400">{p.project} · {p.sold}/{p.parcels} lots vendus</div>
                    </div>
                    <div className="text-right">
                      <div className={`text-lg font-extrabold ${b.text}`}>{p.score}<span className="text-xs text-slate-400">/100</span></div>
                      <div className={`text-[10px] font-semibold uppercase ${b.text}`}>{p.band}</div>
                    </div>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full" style={{ width: `${p.score}%`, background: b.bar }} />
                  </div>
                  <div className="mt-1.5 flex gap-3 text-[11px] text-slate-500">
                    <span>Construction {p.construction}%</span>
                    <span>Paiement {p.payment}%</span>
                    <span>Commercialisation {p.commercialisation}%</span>
                  </div>
                </Link>
              )
            })}
          </div>
        </section>
      </div>

      {/* Clients à risque (IDCP) */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-slate-900">Clients à risque — Indice de Déséquilibre Construction / Paiement</h2>
            <p className="text-xs text-slate-500">Paiement en avance sur l'avancement des travaux — {data.at_risk_total} dossier(s) critiques ou élevés</p>
          </div>
          <Link to="/pilotage/risques" className="shrink-0 text-sm font-medium text-orange-600 hover:underline">Tout voir →</Link>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-600">
              <tr>
                <th className="px-3 py-2">Client</th>
                <th className="px-3 py-2">Programme</th>
                <th className="px-3 py-2">Lot</th>
                <th className="px-3 py-2 text-right">Payé</th>
                <th className="px-3 py-2 text-right">Construction</th>
                <th className="px-3 py-2 text-right">IDCP</th>
                <th className="px-3 py-2">Niveau</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.clients_at_risk.map((r) => {
                const s = levelStyle(r.level)
                return (
                  <tr key={r.sale_id} className="hover:bg-orange-50/30">
                    <td className="px-3 py-2 font-medium text-slate-800">{r.customer}</td>
                    <td className="px-3 py-2 text-slate-600">{r.program}</td>
                    <td className="px-3 py-2 text-slate-600">{r.lot}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-700">{r.payment_pct}%</td>
                    <td className="px-3 py-2 text-right tabular-nums text-slate-700">{r.construction_pct}%</td>
                    <td className={`px-3 py-2 text-right font-bold tabular-nums ${r.idcp >= 20 ? 'text-rose-600' : 'text-slate-700'}`}>
                      {r.idcp > 0 ? '+' : ''}{r.idcp}%
                    </td>
                    <td className="px-3 py-2"><span className={`rounded-full px-2 py-0.5 text-xs font-medium ${s.bg} ${s.text}`}>{s.label}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
