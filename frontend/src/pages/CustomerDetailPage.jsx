import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { deleteResource, getCustomerSummary } from '../api/resources'
import { useCopilotContext } from '../copilot/pageContext'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toasts'
import { badgeClass } from '../lib/badges'
import { formatDate } from '../lib/format'

const card = 'rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800'
const th = 'px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400'
const td = 'px-3 py-2 text-sm text-slate-700 dark:text-slate-200'

function Kpi({ label, value, accent }) {
  return (
    <div className={`${card} px-4 py-3`}>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${accent || 'text-slate-900 dark:text-white'}`}>{value}</div>
    </div>
  )
}

function Section({ title, count, children }) {
  return (
    <section className={`${card} overflow-hidden`}>
      <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-700">
        <h2 className="text-sm font-semibold text-slate-900 dark:text-white">{title}</h2>
        {count != null && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
            {count}
          </span>
        )}
      </header>
      {children}
    </section>
  )
}

function Empty({ children }) {
  return <p className="px-4 py-6 text-sm text-slate-400 dark:text-slate-500">{children}</p>
}

export default function CustomerDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)

  useCopilotContext({ customer_id: id })

  const load = useCallback(() => {
    const controller = new AbortController()
    getCustomerSummary(id, { signal: controller.signal }).then(setData).catch((err) => {
      if (err.name !== 'AbortError') setError(err)
    })
    return () => controller.abort()
  }, [id])

  useEffect(() => load(), [load])

  async function onDelete() {
    setBusy(true)
    try {
      await deleteResource('customers', id)
      toast('Client supprimé.', 'success')
      navigate('/r/customers')
    } catch (err) {
      toast(err.message || 'Suppression impossible.', 'error')
    } finally {
      setBusy(false)
      setConfirmDelete(false)
    }
  }

  if (error) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <Link to="/r/customers" className="text-sm font-medium text-orange-600 hover:underline">← Clients</Link>
        <p className="mt-4 text-sm text-red-600">Erreur : {error.message}</p>
      </div>
    )
  }
  if (!data) {
    return <div className="mx-auto max-w-5xl px-4 py-8 text-sm text-slate-400">Chargement…</div>
  }

  const c = data.customer || {}
  const t = data.totals || {}

  return (
    <div className="mx-auto max-w-5xl space-y-5 px-4 py-6">
      <div>
        <Link to="/r/customers" className="text-sm font-medium text-orange-600 hover:underline">← Clients</Link>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{c.display_name || '—'}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              {c.customer_type_display && (
                <span className={badgeClass(c.customer_type_display)}>{c.customer_type_display}</span>
              )}
              {c.created_at && <span>Client depuis {formatDate(c.created_at)}</span>}
            </div>
          </div>
          <div className="flex gap-2">
            <Link to={`/r/customers/${id}/edit`}
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

      {/* KPIs financiers */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kpi label="Total dû (net)" value={t.total_net ?? '—'} />
        <Kpi label="Total payé" value={t.total_paid ?? '—'} accent="text-emerald-600 dark:text-emerald-400" />
        <Kpi label="Solde" value={t.balance ?? '—'} accent="text-orange-600 dark:text-orange-400" />
        <Kpi label="Taux de paiement" value={t.payment_pct != null ? `${t.payment_pct}%` : '—'}
          accent={t.payment_pct > 100 ? 'text-red-600 dark:text-red-400' : undefined} />
      </div>

      {/* Coordonnées */}
      <Section title="Coordonnées & pièce d'identité">
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 px-4 py-4 text-sm sm:grid-cols-2">
          {[
            ['Téléphone', c.phone], ['Email', c.email], ['Adresse', c.address],
            ['Type de pièce', c.id_type], ['N° de pièce', c.id_number], ['Notes', c.notes],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4 border-b border-slate-50 py-1 dark:border-slate-700/50">
              <dt className="text-slate-500 dark:text-slate-400">{label}</dt>
              <dd className="text-right font-medium text-slate-800 dark:text-slate-100">{value || '—'}</dd>
            </div>
          ))}
        </dl>
      </Section>

      {/* Dossiers de vente / lots */}
      <Section title="Dossiers de vente & lots" count={data.sales?.length || 0}>
        {data.sales?.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-700">
              <thead className="bg-slate-50 dark:bg-slate-900/40">
                <tr>
                  <th className={th}>Programme</th><th className={th}>Lot</th>
                  <th className={th}>Statut</th><th className={`${th} text-right`}>Prix net</th>
                  <th className={`${th} text-right`}>Payé</th><th className={`${th} text-right`}>%</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
                {data.sales.map((s) => (
                  <tr key={s.id}>
                    <td className={td}>{s.program || '—'}</td>
                    <td className={td}>
                      {s.parcel_id
                        ? <Link to={`/r/parcels/${s.parcel_id}`} className="text-orange-600 hover:underline">{s.lot || '—'}</Link>
                        : (s.lot || '—')}
                    </td>
                    <td className={td}>{s.status ? <span className={badgeClass(s.status)}>{s.status}</span> : '—'}</td>
                    <td className={`${td} text-right`}>{s.net_price}</td>
                    <td className={`${td} text-right`}>{s.paid}</td>
                    <td className={`${td} text-right font-semibold ${s.overpaid ? 'text-red-600 dark:text-red-400' : ''}`}>
                      {s.payment_pct}%
                      {s.overpaid && (
                        <span title="Paiements supérieurs au prix net — donnée à vérifier (paiement groupé ou saisie)"
                          className="ml-1 cursor-help">⚠️</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>Aucun dossier de vente.</Empty>}
      </Section>

      {/* Historique des paiements */}
      <Section title="Historique des paiements" count={data.payments?.length || 0}>
        {data.payments?.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-700">
              <thead className="bg-slate-50 dark:bg-slate-900/40">
                <tr>
                  <th className={th}>Date</th><th className={th}>Dossier</th>
                  <th className={th}>Mode</th><th className={th}>Statut</th>
                  <th className={`${th} text-right`}>Montant</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
                {data.payments.map((p) => (
                  <tr key={p.id}>
                    <td className={td}>{p.date ? formatDate(p.date) : '—'}</td>
                    <td className={td}>{p.sale_number || '—'}</td>
                    <td className={td}>{p.method || '—'}</td>
                    <td className={td}><span className={badgeClass(p.status)}>{p.status}</span></td>
                    <td className={`${td} text-right`}>{p.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>Aucun paiement enregistré.</Empty>}
      </Section>

      {/* Réservations */}
      <Section title="Réservations" count={data.reservations?.length || 0}>
        {data.reservations?.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-700">
              <thead className="bg-slate-50 dark:bg-slate-900/40">
                <tr>
                  <th className={th}>N°</th><th className={th}>Programme</th><th className={th}>Lot</th>
                  <th className={th}>Statut</th><th className={th}>Date</th>
                  <th className={`${th} text-right`}>Prix réservé</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
                {data.reservations.map((r) => (
                  <tr key={r.id}>
                    <td className={td}>{r.reservation_number || '—'}</td>
                    <td className={td}>{r.program || '—'}</td>
                    <td className={td}>{r.lot || '—'}</td>
                    <td className={td}>{r.status ? <span className={badgeClass(r.status)}>{r.status}</span> : '—'}</td>
                    <td className={td}>{r.reservation_date ? formatDate(r.reservation_date) : '—'}</td>
                    <td className={`${td} text-right`}>{r.reserved_price}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <Empty>Aucune réservation.</Empty>}
      </Section>

      <ConfirmDialog
        open={confirmDelete}
        title="Supprimer ce client ?"
        message="Le client sera désactivé. Ses dossiers de vente et paiements restent en base."
        confirmLabel={busy ? 'Suppression…' : 'Supprimer'}
        danger
        onConfirm={onDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  )
}
