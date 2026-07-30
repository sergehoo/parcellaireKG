import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getParcelSummary } from '../api/resources'
import { useCopilotContext } from '../copilot/pageContext'
import { badgeClass } from '../lib/badges'
import { levelStyle } from '../lib/criticality'
import { formatDate } from '../lib/format'

const card = 'rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800'
const th = 'px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400'
const td = 'px-3 py-2 text-sm text-slate-700 dark:text-slate-200'

function Row({ label, value, badge }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-50 px-4 py-2.5 last:border-0 dark:border-slate-700/50">
      <span className="text-sm text-slate-500 dark:text-slate-400">{label}</span>
      {badge
        ? <span className={badgeClass(value)}>{value}</span>
        : <span className="text-right text-sm font-medium text-slate-800 dark:text-slate-100">{value ?? '—'}</span>}
    </div>
  )
}

function Section({ title, children, right }) {
  return (
    <section className={`${card} overflow-hidden`}>
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-700">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-white">{title}</h2>
        {right}
      </header>
      {children}
    </section>
  )
}

export default function ParcelDetailPage() {
  const { id } = useParams()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useCopilotContext({ parcel_id: id })

  const load = useCallback(() => {
    const controller = new AbortController()
    getParcelSummary(id, { signal: controller.signal }).then(setData).catch((err) => {
      if (err.name !== 'AbortError') setError(err)
    })
    return () => controller.abort()
  }, [id])

  useEffect(() => load(), [load])

  if (error) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <Link to="/r/parcels" className="text-sm font-medium text-orange-600 hover:underline">← Parcelles</Link>
        <p className="mt-4 text-sm text-red-600">Erreur : {error.message}</p>
      </div>
    )
  }
  if (!data) return <div className="mx-auto max-w-4xl px-4 py-8 text-sm text-slate-400">Chargement…</div>

  const p = data.parcel || {}
  const sale = data.sale
  const cust = data.customer
  const idcp = data.idcp
  const yn = (v) => (v === true ? 'Oui' : v === false ? 'Non' : '—')

  return (
    <div className="mx-auto max-w-4xl space-y-5 px-4 py-6">
      <div>
        <Link to="/r/parcels" className="text-sm font-medium text-orange-600 hover:underline">← Parcelles</Link>
        <h1 className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">
          {p.lot_number ? `Lot ${p.lot_number}` : (p.parcel_code || `#${p.id}`)}
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{p.program_label || '—'}</p>
      </div>

      {/* Client rattaché + vente — la mise en avant demandée */}
      <Section
        title="Client rattaché"
        right={idcp?.level && (
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${levelStyle(idcp.level).bg} ${levelStyle(idcp.level).text}`}>
            {levelStyle(idcp.level).label}
          </span>
        )}
      >
        {cust ? (
          <div className="space-y-4 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <Link to={`/r/customers/${cust.id}`}
                  className="text-lg font-semibold text-orange-600 hover:underline dark:text-orange-400">
                  {cust.display_name}
                </Link>
                <div className="mt-0.5 flex flex-wrap gap-3 text-sm text-slate-500 dark:text-slate-400">
                  {cust.customer_type && <span>{cust.customer_type}</span>}
                  {cust.phone && <span>{cust.phone}</span>}
                  {cust.email && <span>{cust.email}</span>}
                </div>
              </div>
              {sale?.sale_number && (
                <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
                  Dossier {sale.sale_number}
                </span>
              )}
            </div>

            {/* Bloc paiement */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className={`${card} px-3 py-2`}>
                <div className="text-xs text-slate-500 dark:text-slate-400">Prix net</div>
                <div className="text-sm font-semibold text-slate-900 dark:text-white">{sale?.net_price ?? '—'}</div>
              </div>
              <div className={`${card} px-3 py-2`}>
                <div className="text-xs text-slate-500 dark:text-slate-400">Payé</div>
                <div className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">{sale?.paid ?? '—'}</div>
              </div>
              <div className={`${card} px-3 py-2`}>
                <div className="text-xs text-slate-500 dark:text-slate-400">Taux de paiement</div>
                <div className={`text-sm font-semibold ${idcp?.overpaid ? 'text-red-600 dark:text-red-400' : 'text-slate-900 dark:text-white'}`}>
                  {idcp ? `${idcp.payment_pct}%` : '—'}
                  {idcp?.overpaid && (
                    <span title="Paiements supérieurs au prix net — à vérifier" className="ml-1 cursor-help">⚠️</span>
                  )}
                </div>
              </div>
              <div className={`${card} px-3 py-2`}>
                <div className="text-xs text-slate-500 dark:text-slate-400">Construction</div>
                <div className="text-sm font-semibold text-slate-900 dark:text-white">
                  {data.construction?.tracked ? `${data.construction.progress_pct}%` : 'Non suivi'}
                </div>
              </div>
            </div>
            {idcp?.reason && (
              <p className="text-xs text-slate-400 dark:text-slate-500">
                IDCP {idcp.idcp > 0 ? `+${idcp.idcp}` : idcp.idcp}% — {idcp.reason}
              </p>
            )}
          </div>
        ) : (
          <p className="px-4 py-6 text-sm text-slate-400 dark:text-slate-500">
            Aucun client rattaché (parcelle non vendue).
          </p>
        )}
      </Section>

      {/* Caractéristiques de la parcelle */}
      <Section title="Caractéristiques">
        <div className="grid grid-cols-1 sm:grid-cols-2">
          <Row label="Programme" value={p.program_label} />
          <Row label="Statut commercial" value={p.commercial_status_display || p.commercial_status} badge />
          <Row label="Statut technique" value={p.technical_status} />
          <Row label="Surface" value={p.area} />
          <Row label="Viabilisé" value={yn(p.is_serviced)} />
          <Row label="Accès route" value={yn(p.has_road_access)} />
          <Row label="Lot d'angle" value={yn(p.is_corner)} />
          <Row label="Titre foncier" value={p.title_number} />
          <Row label="Géométrie carto" value={data.has_geometry ? 'Oui' : 'Non'} />
          <Row label="Créé le" value={p.created_at ? formatDate(p.created_at) : '—'} />
        </div>
      </Section>

      {/* Historique des paiements */}
      {sale && (
        <Section title="Historique des paiements" right={
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
            {data.payments?.length || 0}
          </span>
        }>
          {data.payments?.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-700">
                <thead className="bg-slate-50 dark:bg-slate-900/40">
                  <tr>
                    <th className={th}>Date</th><th className={th}>Mode</th>
                    <th className={th}>Statut</th><th className={`${th} text-right`}>Montant</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
                  {data.payments.map((pay) => (
                    <tr key={pay.id}>
                      <td className={td}>{pay.date ? formatDate(pay.date) : '—'}</td>
                      <td className={td}>{pay.method || '—'}</td>
                      <td className={td}><span className={badgeClass(pay.status)}>{pay.status}</span></td>
                      <td className={`${td} text-right`}>{pay.amount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="px-4 py-6 text-sm text-slate-400 dark:text-slate-500">Aucun paiement enregistré.</p>}
        </Section>
      )}

      {/* Réservation */}
      {data.reservation && (
        <Section title="Réservation">
          <div className="grid grid-cols-1 sm:grid-cols-2">
            <Row label="N°" value={data.reservation.reservation_number} />
            <Row label="Statut" value={data.reservation.status} badge />
            <Row label="Client" value={data.reservation.customer} />
            <Row label="Date" value={data.reservation.reservation_date ? formatDate(data.reservation.reservation_date) : '—'} />
            <Row label="Prix réservé" value={data.reservation.reserved_price} />
          </div>
        </Section>
      )}
    </div>
  )
}
