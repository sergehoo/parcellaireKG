import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  deleteOrthophotoTiles,
  getOrthophoto,
  getOrthophotoStatus,
  logsDownloadUrl,
  retryOrthophoto,
  setCurrentOrthophoto,
} from '../api/orthophotos'
import StatusBadge from '../components/StatusBadge'
import ProgressBar from '../components/ProgressBar'
import LogTimeline from '../components/LogTimeline'
import TileMapPreview from '../components/TileMapPreview'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/Toasts'
import { formatDateTime, periodLabel } from '../lib/format'

const POLL_INTERVAL_MS = 3000

export default function OrthophotoDetail() {
  const { id } = useParams()
  const toast = useToast()
  const [ortho, setOrtho] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null) // 'delete-tiles' | 'retry'

  const load = useCallback(() => {
    getOrthophoto(id)
      .then((data) => { setOrtho(data); setError(null) })
      .catch((err) => setError(err))
  }, [id])

  useEffect(() => { load() }, [load])

  // Polling toutes les 3 s tant que le pipeline tourne (endpoint léger,
  // puis re-fetch complet quand le statut se stabilise).
  const inProgress = ortho && (ortho.status === 'PENDING' || ortho.status === 'PROCESSING')
  useEffect(() => {
    if (!inProgress) return undefined
    const interval = setInterval(async () => {
      try {
        const status = await getOrthophotoStatus(id)
        setOrtho((current) => (current ? { ...current, ...status, logs: current.logs } : current))
        if (status.status !== 'PENDING' && status.status !== 'PROCESSING') load()
      } catch {
        /* erreur transitoire de polling : on retentera au tick suivant */
      }
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [inProgress, id, load])

  // Recharge les logs pendant le traitement (moins souvent que le statut).
  useEffect(() => {
    if (!inProgress) return undefined
    const interval = setInterval(load, POLL_INTERVAL_MS * 3)
    return () => clearInterval(interval)
  }, [inProgress, load])

  async function runAction(action, fn, successFallback) {
    setBusy(true)
    try {
      const result = await fn(id)
      toast(result?.detail || successFallback, 'success')
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
      setConfirmAction(null)
    }
  }

  if (error) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-6 text-center text-rose-700">
        {error.message}
        <div className="mt-2">
          <Link to="/" className="text-sm font-medium text-sky-600 hover:underline">← Retour à la liste</Link>
        </div>
      </div>
    )
  }
  if (!ortho) {
    return <div className="py-20 text-center text-slate-500">Chargement…</div>
  }

  const actionButton = 'rounded-lg border px-3.5 py-2 text-sm font-medium disabled:opacity-40'

  return (
    <div>
      <div className="mb-6">
        <Link to="/" className="text-sm text-slate-500 hover:text-slate-700">← Orthophotos</Link>
        <div className="mt-1 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              {ortho.name || periodLabel(ortho)}
            </h1>
            <p className="text-sm text-slate-500">
              {ortho.program.project ? `${ortho.program.project.name} · ` : ''}
              {ortho.program.name} — {periodLabel(ortho)}
              {ortho.is_current && (
                <span className="ml-2 rounded bg-sky-50 px-1.5 py-0.5 text-xs font-medium text-sky-700 ring-1 ring-sky-200">
                  Courante
                </span>
              )}
            </p>
          </div>
          <StatusBadge status={ortho.status} label={ortho.status_display} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Colonne principale */}
        <div className="space-y-6 lg:col-span-2">
          {/* Progression */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 font-semibold text-slate-900">Pipeline de traitement</h2>
            <ProgressBar
              percent={ortho.status === 'DONE' ? 100 : ortho.progress_percent}
              status={ortho.status}
              label={ortho.current_step || ortho.status_display}
            />
            {ortho.status === 'FAILED' && ortho.error_message && (
              <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {ortho.error_message}
              </div>
            )}
            {ortho.processed_at && (
              <p className="mt-3 text-xs text-slate-400">
                Traitement terminé le {formatDateTime(ortho.processed_at)}
              </p>
            )}
          </section>

          {/* Carte */}
          {ortho.status === 'DONE' && ortho.tiles_url && (
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-3 font-semibold text-slate-900">Aperçu des tuiles</h2>
              <TileMapPreview
                tilesUrl={ortho.tiles_url}
                bounds={ortho.bounds}
                minZoom={ortho.min_zoom}
                maxZoom={ortho.max_zoom}
              />
              <p className="mt-2 break-all text-xs text-slate-400">{ortho.tiles_url}</p>
            </section>
          )}

          {/* Logs */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Journal du pipeline</h2>
              <a
                href={logsDownloadUrl(ortho.id)}
                className="text-sm font-medium text-sky-600 hover:underline"
              >
                Télécharger (.txt)
              </a>
            </div>
            <div className="max-h-96 overflow-y-auto pr-1">
              <LogTimeline logs={ortho.logs} />
            </div>
          </section>
        </div>

        {/* Colonne latérale */}
        <div className="space-y-6">
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 font-semibold text-slate-900">Actions</h2>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                disabled={busy || inProgress}
                onClick={() => setConfirmAction('retry')}
                className={`${actionButton} border-sky-300 text-sky-700 hover:bg-sky-50`}
              >
                Relancer le traitement
              </button>
              <button
                type="button"
                disabled={busy || ortho.is_current || ortho.status !== 'DONE'}
                onClick={() => runAction('set-current', setCurrentOrthophoto, 'Orthophoto définie comme courante.')}
                className={`${actionButton} border-slate-300 text-slate-700 hover:bg-slate-50`}
              >
                Définir comme courante
              </button>
              <button
                type="button"
                disabled={busy || inProgress || !ortho.tiles_url}
                onClick={() => setConfirmAction('delete-tiles')}
                className={`${actionButton} border-rose-300 text-rose-700 hover:bg-rose-50`}
              >
                Supprimer les tuiles
              </button>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 font-semibold text-slate-900">Informations</h2>
            <dl className="space-y-2 text-sm">
              <Row label="Zooms" value={`${ortho.min_zoom} → ${ortho.max_zoom}`} />
              <Row label="Version" value={ortho.version || '—'} />
              <Row label="Importée le" value={formatDateTime(ortho.created_at)} />
              <Row label="Par" value={ortho.created_by || '—'} />
              <Row label="Mise à jour" value={formatDateTime(ortho.updated_at)} />
            </dl>
          </section>
        </div>
      </div>

      <ConfirmDialog
        open={confirmAction === 'retry'}
        title="Relancer le traitement ?"
        message="Le pipeline GDAL (reprojection, overviews, tuiles) sera relancé depuis le début. Cela peut prendre plus de 30 minutes pour un gros fichier."
        confirmLabel="Relancer"
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => runAction('retry', retryOrthophoto, 'Traitement relancé.')}
      />
      <ConfirmDialog
        open={confirmAction === 'delete-tiles'}
        title="Supprimer les tuiles ?"
        message="Les tuiles générées seront supprimées du disque et le statut repassera à « En attente ». Le fichier source est conservé : un « Relancer » les régénérera."
        confirmLabel="Supprimer"
        danger
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => runAction('delete-tiles', deleteOrthophotoTiles, 'Tuiles supprimées.')}
      />
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  )
}
