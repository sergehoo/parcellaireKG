import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { deleteResource, getResource } from '../api/resources'
import { getResourceConfig } from '../config/resources'
import useOptions from '../hooks/useOptions'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toasts'
import { badgeClass } from '../lib/badges'
import { formatDate } from '../lib/format'

// Libellés lisibles pour les champs bruts non listés dans les colonnes.
const HIDDEN = new Set(['id', 'metadata', 'created_at', 'updated_at'])

export default function ResourceDetailPage() {
  const { resource, id } = useParams()
  const config = getResourceConfig(resource)
  const navigate = useNavigate()
  const toast = useToast()
  const options = useOptions()
  const [obj, setObj] = useState(null)
  const [error, setError] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    if (!config) return
    getResource(config.endpoint, id).then(setObj).catch(setError)
  }, [config, id])

  useEffect(() => { load() }, [load])

  if (!config) return <div className="py-20 text-center text-slate-500">Ressource inconnue.</div>
  if (error) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-6 text-center text-rose-700">
        {error.message}
        <div className="mt-2"><Link to={`/r/${resource}`} className="text-sm font-medium text-orange-600 hover:underline">← Retour</Link></div>
      </div>
    )
  }
  if (!obj) return <div className="py-20 text-center text-slate-500">Chargement…</div>

  const perms = options?.permissions?.[config.permKey] || {}
  const title = obj[config.titleField] || `#${obj.id}`

  // Rangs à afficher : les libellés lisibles présents dans l'objet.
  const rows = Object.entries(obj).filter(([k, v]) => (
    !HIDDEN.has(k) && typeof v !== 'object' && v !== '' && v !== null
  ))

  async function onDelete() {
    setBusy(true)
    try {
      await deleteResource(config.endpoint, id)
      toast(`${config.singular} supprimé.`, 'success')
      navigate(`/r/${resource}`)
    } catch (err) {
      toast(err.message, 'error')
      setBusy(false)
      setConfirmDelete(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link to={`/r/${resource}`} className="text-sm text-slate-500 hover:text-slate-700">← {config.title}</Link>
      <div className="mt-1 mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        {config.writable && (
          <div className="flex gap-2">
            {perms.change && (
              <Link to={`/r/${resource}/${id}/edit`}
                className="rounded-lg border border-slate-300 px-3.5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                Modifier
              </Link>
            )}
            {perms.delete && (
              <button type="button" onClick={() => setConfirmDelete(true)}
                className="rounded-lg border border-rose-300 px-3.5 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50">
                Supprimer
              </button>
            )}
          </div>
        )}
      </div>

      <dl className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        {rows.map(([key, value], i) => (
          <div key={key} className={`flex items-center justify-between gap-4 px-4 py-3 ${i % 2 ? 'bg-white' : 'bg-slate-50/60'}`}>
            <dt className="text-sm text-slate-500">{labelFor(key)}</dt>
            <dd className="text-right text-sm font-medium text-slate-800">
              {/(_display$|^status|^customer_type)/.test(key)
                ? <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badgeClass(String(value))}`}>{String(value)}</span>
                : /_date$|^created_at$/.test(key) ? formatDate(value) : String(value)}
            </dd>
          </div>
        ))}
      </dl>

      <ConfirmDialog
        open={confirmDelete}
        title={`Supprimer ce ${config.singular.toLowerCase()} ?`}
        message="L'élément sera désactivé (archivé). Cette action peut être annulée côté administration."
        confirmLabel="Supprimer" danger
        onCancel={() => setConfirmDelete(false)}
        onConfirm={onDelete}
      />
      {busy && null}
    </div>
  )
}

function labelFor(key) {
  return key
    .replace(/_display$/, '').replace(/_label$/, '')
    .replace(/_/g, ' ')
    .replace(/^\w/, (c) => c.toUpperCase())
}
