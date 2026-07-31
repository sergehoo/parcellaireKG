import { useMemo, useState } from 'react'

const inputC = 'w-full rounded-lg border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-orange-500 focus:ring-orange-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100'
const labelC = 'mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300'

const ALERT_TYPES = [
  ['PERIODIC_GLOBAL', 'Rapport périodique global'],
  ['PAYMENT_GT_CONSTRUCTION', 'Paiement > construction'],
  ['CONSTRUCTION_STAGNANT', 'Construction sans évolution'],
  ['HIGH_COMM_LOW_CONSTRUCTION', 'Commercialisation ≫ construction'],
  ['SOLD_NO_PROGRESS', 'Lot vendu sans avancement'],
  ['DATA_QUALITY', 'Anomalie de données'],
]
const FREQS = [['WEEKLY', 'Hebdomadaire'], ['BIWEEKLY', 'Quinzaine'], ['MONTHLY', 'Mensuelle'],
  ['CUSTOM', 'Personnalisée'], ['MANUAL', 'Manuelle']]
const SEVERITIES = [['INFORMATION', 'Information'], ['VIGILANCE', 'Vigilance'],
  ['IMPORTANT', 'Important'], ['CRITICAL', 'Critique']]
const DOW = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

export default function AlertConfigForm({ initial, recipients, groups, programs, onSubmit, onCancel, busy }) {
  const [f, setF] = useState(() => ({
    name: '', description: '', alert_type: 'PERIODIC_GLOBAL', frequency: 'WEEKLY',
    day_of_week: 0, day_of_month: 1, custom_interval_days: 7, send_time: '08:00',
    start_date: '', end_date: '', minimum_severity: 'VIGILANCE', include_pdf: true,
    skip_weekends: false, is_active: true, include_all_programs: true,
    recipients: [], recipient_groups: [], programs: [],
    ...(initial || {}),
    send_time: (initial?.send_time || '08:00').slice(0, 5),
  }))
  const set = (k, v) => setF((c) => ({ ...c, [k]: v }))
  const multi = (e) => Array.from(e.target.selectedOptions).map((o) => Number(o.value))

  const scheduleFields = useMemo(() => {
    switch (f.frequency) {
      case 'WEEKLY': return (
        <div><label className={labelC}>Jour de la semaine</label>
          <select className={inputC} value={f.day_of_week} onChange={(e) => set('day_of_week', Number(e.target.value))}>
            {DOW.map((d, i) => <option key={i} value={i}>{d}</option>)}
          </select></div>)
      case 'MONTHLY': return (
        <div><label className={labelC}>Jour du mois (31 = dernier)</label>
          <input type="number" min="1" max="31" className={inputC} value={f.day_of_month}
            onChange={(e) => set('day_of_month', Number(e.target.value))} /></div>)
      case 'CUSTOM': return (
        <div><label className={labelC}>Intervalle (jours)</label>
          <input type="number" min="1" className={inputC} value={f.custom_interval_days}
            onChange={(e) => set('custom_interval_days', Number(e.target.value))} /></div>)
      case 'BIWEEKLY': return (
        <div><label className={labelC}>Date de référence</label>
          <input type="date" className={inputC} value={f.start_date || ''}
            onChange={(e) => set('start_date', e.target.value)} /></div>)
      default: return null
    }
  }, [f.frequency, f.day_of_week, f.day_of_month, f.custom_interval_days, f.start_date])

  function submit(e) {
    e.preventDefault()
    const payload = { ...f }
    if (!payload.start_date) delete payload.start_date
    if (!payload.end_date) delete payload.end_date
    payload.include_all_programs = payload.programs.length === 0
    onSubmit(payload)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><label className={labelC}>Nom *</label>
          <input required className={inputC} value={f.name} onChange={(e) => set('name', e.target.value)} /></div>
        <div><label className={labelC}>Type d'alerte</label>
          <select className={inputC} value={f.alert_type} onChange={(e) => set('alert_type', e.target.value)}>
            {ALERT_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
        <div><label className={labelC}>Sévérité minimale</label>
          <select className={inputC} value={f.minimum_severity} onChange={(e) => set('minimum_severity', e.target.value)}>
            {SEVERITIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
        <div><label className={labelC}>Fréquence</label>
          <select className={inputC} value={f.frequency} onChange={(e) => set('frequency', e.target.value)}>
            {FREQS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
        {f.frequency !== 'MANUAL' && (
          <div><label className={labelC}>Heure d'envoi</label>
            <input type="time" className={inputC} value={f.send_time} onChange={(e) => set('send_time', e.target.value)} /></div>)}
        {scheduleFields}
        {f.frequency !== 'MANUAL' && (
          <div><label className={labelC}>Fin (optionnel)</label>
            <input type="date" className={inputC} value={f.end_date || ''} onChange={(e) => set('end_date', e.target.value)} /></div>)}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div><label className={labelC}>Destinataires</label>
          <select multiple className={`${inputC} h-28`} value={f.recipients.map(String)}
            onChange={(e) => set('recipients', multi(e))}>
            {recipients.map((r) => <option key={r.id} value={r.id}>{r.display_name} — {r.email}</option>)}</select></div>
        <div><label className={labelC}>Groupes</label>
          <select multiple className={`${inputC} h-28`} value={f.recipient_groups.map(String)}
            onChange={(e) => set('recipient_groups', multi(e))}>
            {groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
        <div><label className={labelC}>Programmes (vide = tous)</label>
          <select multiple className={`${inputC} h-28`} value={f.programs.map(String)}
            onChange={(e) => set('programs', multi(e))}>
            {(programs || []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
      </div>

      <div className="flex flex-wrap gap-4 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={f.include_pdf}
          onChange={(e) => set('include_pdf', e.target.checked)} /> Joindre le PDF</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={f.skip_weekends}
          onChange={(e) => set('skip_weekends', e.target.checked)} /> Reporter si week-end</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={f.is_active}
          onChange={(e) => set('is_active', e.target.checked)} /> Active</label>
      </div>

      <div className="flex justify-end gap-2 border-t border-slate-100 pt-3 dark:border-slate-700">
        <button type="button" onClick={onCancel}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm dark:border-slate-600 dark:text-slate-200">Annuler</button>
        <button type="submit" disabled={busy}
          className="rounded-lg bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-60">
          {busy ? 'Enregistrement…' : 'Enregistrer'}</button>
      </div>
    </form>
  )
}
