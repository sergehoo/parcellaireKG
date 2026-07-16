import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { createResource, getResource, updateResource } from '../api/resources'
import { getResourceConfig } from '../config/resources'
import useOptions from '../hooks/useOptions'
import { useToast } from '../components/Toasts'

export default function ResourceFormPage() {
  const { resource, id } = useParams()
  const config = getResourceConfig(resource)
  const isEdit = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()
  const options = useOptions()

  const [form, setForm] = useState({})
  const [loading, setLoading] = useState(isEdit)
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})
  const [topError, setTopError] = useState(null)

  useEffect(() => {
    if (!config || !isEdit) return
    getResource(config.endpoint, id)
      .then((obj) => {
        const initial = {}
        config.fields.forEach((f) => { initial[f.name] = obj[f.name] ?? '' })
        setForm(initial)
      })
      .catch((err) => setTopError(err.message))
      .finally(() => setLoading(false))
  }, [config, id, isEdit])

  // Programmes filtrés par projet sélectionné (pour le champ program).
  const dynamicOptions = useMemo(() => {
    if (!options) return {}
    let programs = options.programs || []
    if (form.project) programs = programs.filter((p) => String(p.project) === String(form.project))
    return { ...options, programs }
  }, [options, form.project])

  if (!config) return <div className="py-20 text-center text-slate-500">Ressource inconnue.</div>
  if (!config.writable) return <div className="py-20 text-center text-slate-500">Ressource en lecture seule.</div>
  if (loading) return <div className="py-20 text-center text-slate-500">Chargement…</div>

  function set(name, value) {
    setForm((f) => ({ ...f, [name]: value }))
    setErrors((e) => ({ ...e, [name]: undefined }))
  }

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    setErrors({}); setTopError(null)
    // Nettoyage : chaînes vides → null pour les FK/dates optionnelles.
    const payload = {}
    config.fields.forEach((f) => {
      let v = form[f.name]
      if (v === '' || v === undefined) v = null
      payload[f.name] = v
    })
    try {
      const saved = isEdit
        ? await updateResource(config.endpoint, id, payload)
        : await createResource(config.endpoint, payload)
      toast(isEdit ? `${config.singular} mis à jour.` : `${config.singular} créé.`, 'success')
      navigate(`/r/${resource}/${saved.id}`)
    } catch (err) {
      if (err.status === 400 && err.data && typeof err.data === 'object') {
        const fieldErrs = {}
        let general = null
        Object.entries(err.data).forEach(([k, val]) => {
          const msg = Array.isArray(val) ? val.join(' ') : String(val)
          if (k === 'non_field_errors' || k === 'detail') general = msg
          else fieldErrs[k] = msg
        })
        setErrors(fieldErrs)
        setTopError(general)
      } else {
        setTopError(err.message)
      }
      setSaving(false)
    }
  }

  const inputCls = 'w-full rounded-lg border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-orange-400 focus:ring-orange-400'

  return (
    <div className="mx-auto max-w-3xl">
      <Link to={isEdit ? `/r/${resource}/${id}` : `/r/${resource}`} className="text-sm text-slate-500 hover:text-slate-700">← Annuler</Link>
      <h1 className="mb-5 mt-1 text-2xl font-bold text-slate-900">
        {isEdit ? `Modifier — ${config.singular}` : `Nouveau ${config.singular.toLowerCase()}`}
      </h1>

      {topError && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{topError}</div>
      )}

      <form onSubmit={submit} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {config.fields.map((f) => {
            const full = f.type === 'textarea' || !f.half
            return (
              <div key={f.name} className={full ? 'sm:col-span-2' : ''}>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  {f.label}{f.required && <span className="text-rose-500"> *</span>}
                </label>
                {f.type === 'select' ? (
                  <select value={form[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)} className={inputCls}>
                    <option value="">—</option>
                    {(dynamicOptions[f.optionsKey] || []).map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                ) : f.type === 'textarea' ? (
                  <textarea rows={3} value={form[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)} className={inputCls} />
                ) : (
                  <input
                    type={f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : f.type === 'email' ? 'email' : 'text'}
                    value={form[f.name] ?? ''} onChange={(e) => set(f.name, e.target.value)} className={inputCls}
                  />
                )}
                {errors[f.name] && <p className="mt-1 text-xs text-rose-600">{errors[f.name]}</p>}
              </div>
            )
          })}
        </div>

        <div className="mt-6 flex justify-end gap-3 border-t border-slate-100 pt-4">
          <Link to={isEdit ? `/r/${resource}/${id}` : `/r/${resource}`}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Annuler
          </Link>
          <button type="submit" disabled={saving}
            className="rounded-lg px-5 py-2 text-sm font-semibold text-white shadow-sm disabled:opacity-50"
            style={{ background: 'var(--kaydan)' }}>
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </form>
    </div>
  )
}
