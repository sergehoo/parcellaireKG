import { useCallback, useEffect, useState } from 'react'
import useReferenceData from '../hooks/useReferenceData'
import { useToast } from '../components/Toasts'
import ConfirmDialog from '../components/ConfirmDialog'
import AlertConfigForm from '../components/alerts/AlertConfigForm'
import {
  acknowledgeDetection, createConfiguration, createRecipient, deleteConfiguration,
  deleteRecipient, downloadReportUrl, generateReport, getAlertDashboard, listConfigurations,
  listDetections, listGroups, listHistory, listRecipients, smtpTest, updateConfiguration,
} from '../api/alerts'

const card = 'rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800'
const th = 'px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400'
const td = 'px-3 py-2 text-sm text-slate-700 dark:text-slate-200'
const btn = 'rounded-lg px-3 py-1.5 text-sm font-medium'

const SEV = {
  CRITICAL: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
  IMPORTANT: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
  VIGILANCE: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
  INFORMATION: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300',
}
const STATUS = {
  SENT: 'bg-emerald-100 text-emerald-700', READY: 'bg-sky-100 text-sky-700',
  PARTIAL: 'bg-amber-100 text-amber-700', FAILED: 'bg-rose-100 text-rose-700',
  PENDING: 'bg-slate-100 text-slate-600', GENERATING: 'bg-slate-100 text-slate-600',
  SENDING: 'bg-sky-100 text-sky-700', CANCELLED: 'bg-slate-100 text-slate-600',
}
const pill = (map, k) => `inline-block rounded-full px-2 py-0.5 text-xs font-medium ${map[k] || 'bg-slate-100 text-slate-600'}`
const dt = (v) => (v ? new Date(v).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : '—')
const rows = (r) => (Array.isArray(r) ? r : (r?.results || []))

function Kpi({ label, value, accent }) {
  return (
    <div className={`${card} px-4 py-3`}>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`mt-1 text-xl font-semibold ${accent || 'text-slate-900 dark:text-white'}`}>{value}</div>
    </div>
  )
}

function Modal({ title, onClose, children, wide }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4">
      <div className={`${card} my-8 w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} p-5`}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export default function AlertsCenterPage() {
  const toast = useToast()
  const { refData } = useReferenceData()
  const [tab, setTab] = useState('configs')
  const [dash, setDash] = useState(null)
  const [configs, setConfigs] = useState([])
  const [recipients, setRecipients] = useState([])
  const [groups, setGroups] = useState([])
  const [detections, setDetections] = useState([])
  const [history, setHistory] = useState([])
  const [editing, setEditing] = useState(null)      // config being created/edited, or null
  const [showGen, setShowGen] = useState(false)
  const [confirmDel, setConfirmDel] = useState(null)
  const [busy, setBusy] = useState(false)

  const loadDash = useCallback(() => { getAlertDashboard().then(setDash).catch(() => {}) }, [])
  const loadConfigs = useCallback(() => { listConfigurations().then((r) => setConfigs(rows(r))).catch(() => {}) }, [])
  const loadRecipients = useCallback(() => {
    listRecipients().then((r) => setRecipients(rows(r))).catch(() => {})
    listGroups().then((r) => setGroups(rows(r))).catch(() => {})
  }, [])
  const loadDetections = useCallback(() => { listDetections({ status: 'NEW' }).then((r) => setDetections(rows(r))).catch(() => {}) }, [])
  const loadHistory = useCallback(() => { listHistory().then((r) => setHistory(rows(r))).catch(() => {}) }, [])

  useEffect(() => { loadDash(); loadConfigs(); loadRecipients() }, [loadDash, loadConfigs, loadRecipients])
  useEffect(() => {
    if (tab === 'detections') loadDetections()
    if (tab === 'history') loadHistory()
  }, [tab, loadDetections, loadHistory])

  async function saveConfig(payload) {
    setBusy(true)
    try {
      if (editing?.id) await updateConfiguration(editing.id, payload)
      else await createConfiguration(payload)
      toast('Configuration enregistrée.', 'success')
      setEditing(null); loadConfigs(); loadDash()
    } catch (e) { toast(e.message || 'Erreur', 'error') } finally { setBusy(false) }
  }

  async function onDeleteConfig(id) {
    try { await deleteConfiguration(id); toast('Supprimée.', 'success'); loadConfigs(); loadDash() }
    catch (e) { toast(e.message || 'Erreur', 'error') } finally { setConfirmDel(null) }
  }

  async function onAck(id) {
    try { await acknowledgeDetection(id); loadDetections(); loadDash() }
    catch (e) { toast(e.message || 'Acquittement impossible (permission ?)', 'error') }
  }

  async function onTestSmtp() {
    const email = window.prompt('Adresse e-mail de test :')
    if (!email) return
    try { const r = await smtpTest(email); toast(r.ok ? `E-mail de test envoyé à ${email}` : 'Échec', r.ok ? 'success' : 'error') }
    catch (e) { toast(e.message || 'Échec SMTP', 'error') }
  }

  const TABS = [['configs', 'Configurations'], ['recipients', 'Destinataires'],
    ['detections', 'Détections'], ['history', 'Historique']]

  return (
    <div className="mx-auto max-w-6xl space-y-5 px-4 py-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Centre des alertes</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">Suivi paiement · construction · commercialisation</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowGen(true)} className={`${btn} bg-orange-600 text-white hover:bg-orange-700`}>Générer maintenant</button>
          <button onClick={onTestSmtp} className={`${btn} border border-slate-300 text-slate-700 dark:border-slate-600 dark:text-slate-200`}>Tester l'envoi</button>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Kpi label="Alertes actives" value={dash?.active_alerts ?? '—'} accent="text-rose-600 dark:text-rose-400" />
        <Kpi label="Lots critiques" value={dash?.critical_lots ?? '—'} accent="text-rose-600 dark:text-rose-400" />
        <Kpi label="Prochain envoi" value={dash?.next_send_at ? dt(dash.next_send_at) : '—'} />
        <Kpi label="Destinataires" value={dash?.active_recipients ?? '—'} />
        <Kpi label="Programmes suivis" value={dash?.monitored_programs ?? '—'} />
        <Kpi label="Rapports ce mois" value={dash?.reports_this_month ?? '—'} accent="text-emerald-600 dark:text-emerald-400" />
        <Kpi label="Échecs d'envoi" value={dash?.failed_dispatches ?? '—'} accent={dash?.failed_dispatches ? 'text-rose-600' : undefined} />
        <Kpi label="Dernier envoi" value={dash?.last_sent_at ? dt(dash.last_sent_at) : '—'} />
        <Kpi label="Service e-mail" value={dash ? (dash.email_service_ok ? 'OK' : 'À configurer') : '—'}
          accent={dash?.email_service_ok ? 'text-emerald-600' : 'text-amber-600'} />
        <Kpi label="Configurations" value={dash?.active_configurations ?? '—'} />
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-700">
        {TABS.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm font-medium ${tab === k ? 'border-b-2 border-orange-600 text-orange-600' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400'}`}>
            {l}
          </button>
        ))}
      </div>

      {tab === 'configs' && (
        <section className={`${card} overflow-hidden`}>
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-700">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Configurations d'alerte</h2>
            <button onClick={() => setEditing({})} className={`${btn} bg-slate-800 text-white dark:bg-white dark:text-slate-900`}>+ Nouvelle alerte</button>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-700">
              <thead className="bg-slate-50 dark:bg-slate-900/40"><tr>
                <th className={th}>Nom</th><th className={th}>Type</th><th className={th}>Fréquence</th>
                <th className={th}>Prochain envoi</th><th className={th}>Sévérité min.</th><th className={th}>Actif</th><th className={th}></th>
              </tr></thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
                {configs.map((c) => (
                  <tr key={c.id}>
                    <td className={td}>{c.name}</td>
                    <td className={td}>{c.alert_type_display}</td>
                    <td className={td}>{c.frequency_display}</td>
                    <td className={td}>{dt(c.next_send_at)}</td>
                    <td className={td}>{c.minimum_severity}</td>
                    <td className={td}>{c.is_active ? '✅' : '—'}</td>
                    <td className={`${td} text-right`}>
                      <button onClick={() => setEditing(c)} className="mr-3 text-orange-600 hover:underline">Modifier</button>
                      <button onClick={() => setConfirmDel(c)} className="text-red-600 hover:underline">Suppr.</button>
                    </td>
                  </tr>
                ))}
                {!configs.length && <tr><td className={`${td} text-slate-400`} colSpan={7}>Aucune configuration.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === 'recipients' && (
        <RecipientsTab recipients={recipients} groups={groups} onChange={loadRecipients} toast={toast} />
      )}

      {tab === 'detections' && (
        <section className={`${card} overflow-hidden`}>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-700">
              <thead className="bg-slate-50 dark:bg-slate-900/40"><tr>
                <th className={th}>Sévérité</th><th className={th}>Alerte</th><th className={th}>Programme</th>
                <th className={th}>Lot</th><th className={`${th} num`}>Écart</th><th className={th}>Détectée</th><th className={th}></th>
              </tr></thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
                {detections.map((d) => (
                  <tr key={d.id}>
                    <td className={td}><span className={pill(SEV, d.severity)}>{d.severity_label}</span></td>
                    <td className={td}>{d.title}</td>
                    <td className={td}>{d.program_name || '—'}</td>
                    <td className={td}>{d.lot_label || '—'}</td>
                    <td className={td}>{d.difference != null ? `${d.difference > 0 ? '+' : ''}${d.difference} pts` : '—'}</td>
                    <td className={td}>{dt(d.detected_at)}</td>
                    <td className={`${td} text-right`}>
                      <button onClick={() => onAck(d.id)} className="text-orange-600 hover:underline">Acquitter</button>
                    </td>
                  </tr>
                ))}
                {!detections.length && <tr><td className={`${td} text-slate-400`} colSpan={7}>Aucune détection active.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {tab === 'history' && (
        <section className={`${card} overflow-hidden`}>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-700">
              <thead className="bg-slate-50 dark:bg-slate-900/40"><tr>
                <th className={th}>Date</th><th className={th}>Objet</th><th className={th}>Période</th>
                <th className={th}>Statut</th><th className={th}>E-mails</th><th className={th}>PDF</th>
              </tr></thead>
              <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
                {history.map((h) => (
                  <tr key={h.id}>
                    <td className={td}>{dt(h.created_at)}</td>
                    <td className={td}>{h.subject || '—'}{h.is_preview && <span className="ml-1 text-xs text-slate-400">(aperçu)</span>}</td>
                    <td className={td}>{h.period_start} → {h.period_end}</td>
                    <td className={td}><span className={pill(STATUS, h.status)}>{h.status_display}</span></td>
                    <td className={td}>{h.email_count}</td>
                    <td className={td}>{h.report ? <a href={downloadReportUrl(h.report.id)} className="text-orange-600 hover:underline">Télécharger</a> : '—'}</td>
                  </tr>
                ))}
                {!history.length && <tr><td className={`${td} text-slate-400`} colSpan={6}>Aucun envoi.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {editing !== null && (
        <Modal wide title={editing.id ? 'Modifier la configuration' : 'Nouvelle alerte'} onClose={() => setEditing(null)}>
          <AlertConfigForm initial={editing.id ? editing : null} recipients={recipients} groups={groups}
            programs={refData?.programs || []} busy={busy} onCancel={() => setEditing(null)} onSubmit={saveConfig} />
        </Modal>
      )}

      {showGen && (
        <GenerateModal programs={refData?.programs || []} onClose={() => setShowGen(false)} toast={toast}
          onDone={() => { setShowGen(false); loadHistory(); loadDash() }} />
      )}

      <ConfirmDialog open={!!confirmDel} title="Supprimer la configuration ?"
        message={confirmDel ? `« ${confirmDel.name} » sera supprimée.` : ''} danger confirmLabel="Supprimer"
        onConfirm={() => onDeleteConfig(confirmDel.id)} onCancel={() => setConfirmDel(null)} />
    </div>
  )
}

function RecipientsTab({ recipients, groups, onChange, toast }) {
  const [form, setForm] = useState({ email: '', first_name: '', last_name: '', department: '', receive_pdf: true })
  const set = (k, v) => setForm((c) => ({ ...c, [k]: v }))
  async function add(e) {
    e.preventDefault()
    try { await createRecipient(form); toast('Destinataire ajouté.', 'success'); setForm({ email: '', first_name: '', last_name: '', department: '', receive_pdf: true }); onChange() }
    catch (err) { toast(err.message || 'Erreur', 'error') }
  }
  async function remove(id) {
    try { await deleteRecipient(id); onChange() } catch (err) { toast(err.message || 'Erreur', 'error') }
  }
  const inputC = 'rounded-lg border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100'
  return (
    <div className="space-y-4">
      <form onSubmit={add} className={`${card} flex flex-wrap items-end gap-2 p-4`}>
        <input required type="email" placeholder="E-mail *" className={inputC} value={form.email} onChange={(e) => set('email', e.target.value)} />
        <input placeholder="Prénom" className={inputC} value={form.first_name} onChange={(e) => set('first_name', e.target.value)} />
        <input placeholder="Nom" className={inputC} value={form.last_name} onChange={(e) => set('last_name', e.target.value)} />
        <input placeholder="Direction" className={inputC} value={form.department} onChange={(e) => set('department', e.target.value)} />
        <button className={`${btn} bg-orange-600 text-white hover:bg-orange-700`}>Ajouter</button>
      </form>
      <section className={`${card} overflow-hidden`}>
        <div className="border-b border-slate-100 px-4 py-2 text-xs font-semibold uppercase text-slate-500 dark:border-slate-700">
          Destinataires ({recipients.length}) · Groupes ({groups.length})
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-100 dark:divide-slate-700">
            <thead className="bg-slate-50 dark:bg-slate-900/40"><tr>
              <th className={th}>Nom</th><th className={th}>E-mail</th><th className={th}>Direction</th><th className={th}>PDF</th><th className={th}></th>
            </tr></thead>
            <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
              {recipients.map((r) => (
                <tr key={r.id}>
                  <td className={td}>{r.display_name}</td><td className={td}>{r.email}</td>
                  <td className={td}>{r.department || '—'}</td><td className={td}>{r.receive_pdf ? '✅' : '—'}</td>
                  <td className={`${td} text-right`}><button onClick={() => remove(r.id)} className="text-red-600 hover:underline">Retirer</button></td>
                </tr>
              ))}
              {!recipients.length && <tr><td className={`${td} text-slate-400`} colSpan={5}>Aucun destinataire.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function GenerateModal({ programs, onClose, onDone, toast }) {
  const [f, setF] = useState({ period_days: 7, minimum_severity: 'VIGILANCE', include_pdf: true, program_ids: [], preview: true })
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const set = (k, v) => setF((c) => ({ ...c, [k]: v }))
  const inputC = 'w-full rounded-lg border-slate-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100'
  async function run(preview) {
    setBusy(true)
    try {
      const r = await generateReport({ ...f, preview })
      setResult(r)
      toast(preview ? 'Aperçu généré.' : `Rapport envoyé (${r.email_count} e-mail(s)).`, 'success')
      if (!preview) onDone()
    } catch (e) { toast(e.message || 'Erreur de génération', 'error') } finally { setBusy(false) }
  }
  return (
    <Modal title="Générer un rapport" onClose={onClose}>
      <div className="space-y-3">
        <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Période (jours)</label>
          <input type="number" min="1" className={inputC} value={f.period_days} onChange={(e) => set('period_days', Number(e.target.value))} /></div>
        <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Sévérité minimale</label>
          <select className={inputC} value={f.minimum_severity} onChange={(e) => set('minimum_severity', e.target.value)}>
            {['INFORMATION', 'VIGILANCE', 'IMPORTANT', 'CRITICAL'].map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
        <div><label className="mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300">Programmes (vide = tous)</label>
          <select multiple className={`${inputC} h-24`} value={f.program_ids.map(String)}
            onChange={(e) => set('program_ids', Array.from(e.target.selectedOptions).map((o) => Number(o.value)))}>
            {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
        {result?.report && (
          <div className="rounded-lg bg-emerald-50 p-3 text-sm dark:bg-emerald-900/20">
            Aperçu prêt — <a href={downloadReportUrl(result.report.id)} className="font-medium text-orange-600 hover:underline">télécharger le PDF</a>
          </div>
        )}
        <div className="flex justify-end gap-2 border-t border-slate-100 pt-3 dark:border-slate-700">
          <button onClick={() => run(true)} disabled={busy} className={`${btn} border border-slate-300 dark:border-slate-600 dark:text-slate-200`}>Prévisualiser</button>
          <button onClick={() => run(false)} disabled={busy} className={`${btn} bg-orange-600 text-white hover:bg-orange-700 disabled:opacity-60`}>
            {busy ? '…' : 'Générer & envoyer'}</button>
        </div>
      </div>
    </Modal>
  )
}
