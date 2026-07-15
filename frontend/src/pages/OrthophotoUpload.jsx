import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadAbort, uploadComplete, uploadInit } from '../api/orthophotos'
import { uploadFileMultipart } from '../lib/uploadMultipart'
import useReferenceData from '../hooks/useReferenceData'
import FileDropzone from '../components/FileDropzone'
import { formatBytes, monthName } from '../lib/format'
import { useToast } from '../components/Toasts'

const MAX_BYTES = 8 * 1024 * 1024 * 1024 // 8 Go, aligné sur ORTHOPHOTO_MAX_BYTES

const initialForm = {
  project: '',
  program: '',
  name: '',
  period_label: '',
  reference_year: '',
  reference_month: '',
  min_zoom: 15,
  max_zoom: 22,
  is_current: true,
  replace_existing: false,
}

export default function OrthophotoUpload() {
  const navigate = useNavigate()
  const toast = useToast()
  const { refData } = useReferenceData()

  const [form, setForm] = useState(initialForm)
  const [file, setFile] = useState(null)
  const [phase, setPhase] = useState('idle') // idle | uploading | finalizing
  const [sentBytes, setSentBytes] = useState(0)
  const [error, setError] = useState(null)
  const [conflict, setConflict] = useState(null)
  const abortRef = useRef(null)
  const orthoIdRef = useRef(null)

  const programs = useMemo(() => {
    if (!refData) return []
    return form.project
      ? refData.programs.filter((p) => String(p.project_id) === String(form.project))
      : refData.programs
  }, [refData, form.project])

  function update(key, value) {
    setForm((current) => ({
      ...current,
      [key]: value,
      ...(key === 'project' ? { program: '' } : {}),
    }))
    setConflict(null)
    setError(null)
  }

  const canSubmit = file && form.program && phase === 'idle'
    && Number(form.min_zoom) <= Number(form.max_zoom)

  async function submit({ replaceExisting = false } = {}) {
    if (!file || !form.program) return
    setError(null)
    setConflict(null)
    setSentBytes(0)
    setPhase('uploading')

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const session = await uploadInit({
        program: form.program,
        name: form.name,
        period_label: form.period_label,
        reference_year: form.reference_year || null,
        reference_month: form.reference_month || null,
        min_zoom: Number(form.min_zoom),
        max_zoom: Number(form.max_zoom),
        is_current: form.is_current,
        replace_existing: replaceExisting || form.replace_existing,
        filename: file.name,
        total_size: file.size,
      })
      orthoIdRef.current = session.orthophoto_id

      const parts = await uploadFileMultipart(file, session, {
        signal: controller.signal,
        onProgress: (sent) => setSentBytes(sent),
      })

      setPhase('finalizing')
      const done = await uploadComplete({
        orthophoto_id: session.orthophoto_id,
        parts,
      })
      toast('Upload terminé — traitement GDAL lancé.', 'success')
      navigate(`/orthophotos/${done.orthophoto_id}`)
    } catch (err) {
      if (err.name === 'AbortError') {
        if (orthoIdRef.current) uploadAbort(orthoIdRef.current).catch(() => {})
        setError('Upload annulé.')
      } else if (err.status === 409 && err.data?.conflict) {
        setConflict(err.data)
      } else {
        if (orthoIdRef.current) uploadAbort(orthoIdRef.current).catch(() => {})
        setError(err.message)
      }
      setPhase('idle')
    } finally {
      abortRef.current = null
    }
  }

  const inputClass = 'w-full rounded-lg border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-sky-500 focus:ring-sky-500'
  const labelClass = 'mb-1 block text-sm font-medium text-slate-700'
  const uploading = phase !== 'idle'
  const percent = file ? Math.round((sentBytes / file.size) * 100) : 0

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold text-slate-900">Nouvelle orthophoto</h1>
      <p className="mb-6 text-sm text-slate-500">
        Le fichier est envoyé directement vers le stockage S3 (MinIO) par morceaux,
        puis le pipeline GDAL génère les tuiles en arrière-plan.
      </p>

      <div className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <FileDropzone file={file} onFile={setFile} disabled={uploading} maxBytes={MAX_BYTES} />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className={labelClass}>Projet</label>
            <select
              value={form.project}
              onChange={(e) => update('project', e.target.value)}
              disabled={uploading}
              className={inputClass}
            >
              <option value="">— Tous —</option>
              {refData?.projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className={labelClass}>Programme *</label>
            <select
              value={form.program}
              onChange={(e) => update('program', e.target.value)}
              disabled={uploading}
              className={inputClass}
            >
              <option value="">— Choisir —</option>
              {programs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
          <div>
            <label className={labelClass}>Nom (optionnel)</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => update('name', e.target.value)}
              placeholder="ex. Survol drone mai"
              disabled={uploading}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Libellé période (optionnel)</label>
            <input
              type="text"
              value={form.period_label}
              onChange={(e) => update('period_label', e.target.value)}
              placeholder="ex. Mai 2026"
              disabled={uploading}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Année de référence</label>
            <select
              value={form.reference_year}
              onChange={(e) => update('reference_year', e.target.value)}
              disabled={uploading}
              className={inputClass}
            >
              <option value="">—</option>
              {refData?.years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          <div>
            <label className={labelClass}>Mois de référence</label>
            <select
              value={form.reference_month}
              onChange={(e) => update('reference_month', e.target.value)}
              disabled={uploading}
              className={inputClass}
            >
              <option value="">—</option>
              {refData?.months.map((m) => <option key={m} value={m}>{monthName(m)}</option>)}
            </select>
          </div>
          <div>
            <label className={labelClass}>Zoom min</label>
            <input
              type="number" min={1} max={24}
              value={form.min_zoom}
              onChange={(e) => update('min_zoom', e.target.value)}
              disabled={uploading}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Zoom max</label>
            <input
              type="number" min={1} max={24}
              value={form.max_zoom}
              onChange={(e) => update('max_zoom', e.target.value)}
              disabled={uploading}
              className={inputClass}
            />
          </div>
        </div>

        {Number(form.min_zoom) > Number(form.max_zoom) && (
          <p className="text-sm text-rose-600">Le zoom min ne peut pas dépasser le zoom max.</p>
        )}

        <div className="flex flex-wrap gap-6">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={form.is_current}
              onChange={(e) => update('is_current', e.target.checked)}
              disabled={uploading}
              className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            Définir comme orthophoto courante
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={form.replace_existing}
              onChange={(e) => update('replace_existing', e.target.checked)}
              disabled={uploading}
              className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            Remplacer si la période existe déjà
          </label>
        </div>

        {conflict && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <p className="font-medium">Une orthophoto existe déjà pour ce programme / cette période.</p>
            <div className="mt-2 flex gap-3">
              <button
                type="button"
                onClick={() => submit({ replaceExisting: true })}
                className="rounded-lg bg-amber-600 px-3 py-1.5 font-medium text-white hover:bg-amber-700"
              >
                Remplacer l'existante
              </button>
              <button
                type="button"
                onClick={() => navigate(`/orthophotos/${conflict.existing_id}`)}
                className="rounded-lg border border-amber-400 px-3 py-1.5 font-medium hover:bg-amber-100"
              >
                Voir l'existante
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {uploading && file && (
          <div>
            <div className="mb-1 flex justify-between text-sm text-slate-600">
              <span>
                {phase === 'finalizing'
                  ? 'Finalisation S3…'
                  : `Envoi vers S3 — ${formatBytes(sentBytes)} / ${formatBytes(file.size)}`}
              </span>
              <span className="font-medium">{phase === 'finalizing' ? '100' : percent}%</span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-sky-500 transition-all"
                style={{ width: `${phase === 'finalizing' ? 100 : percent}%` }}
              />
            </div>
          </div>
        )}

        <div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-4">
          {uploading ? (
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              className="rounded-lg border border-rose-300 px-4 py-2 text-sm font-medium text-rose-700 hover:bg-rose-50"
            >
              Annuler l'upload
            </button>
          ) : (
            <button
              type="button"
              disabled={!canSubmit}
              onClick={() => submit()}
              className="rounded-lg bg-sky-600 px-5 py-2 text-sm font-medium text-white shadow-sm hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Lancer l'import
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
