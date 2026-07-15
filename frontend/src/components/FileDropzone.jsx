import { useRef, useState } from 'react'
import { formatBytes } from '../lib/format'

const ACCEPTED = ['.tif', '.tiff']

export default function FileDropzone({ file, onFile, disabled, maxBytes }) {
  const inputRef = useRef(null)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState(null)

  function validateAndSet(candidate) {
    setError(null)
    if (!candidate) return
    const name = candidate.name.toLowerCase()
    if (!ACCEPTED.some((ext) => name.endsWith(ext))) {
      setError('Seuls les fichiers GeoTIFF (.tif, .tiff) sont acceptés.')
      return
    }
    if (maxBytes && candidate.size > maxBytes) {
      setError(`Fichier trop volumineux (max ${formatBytes(maxBytes)}).`)
      return
    }
    onFile(candidate)
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && !disabled && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (!disabled) validateAndSet(e.dataTransfer.files?.[0])
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition
          ${dragOver ? 'border-sky-400 bg-sky-50' : 'border-slate-300 bg-white hover:border-slate-400'}
          ${disabled ? 'pointer-events-none opacity-60' : ''}`}
      >
        <svg className="mb-3 h-10 w-10 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        {file ? (
          <>
            <p className="font-medium text-slate-800">{file.name}</p>
            <p className="mt-1 text-sm text-slate-500">{formatBytes(file.size)}</p>
            <p className="mt-2 text-xs text-sky-600">Cliquer ou déposer pour remplacer</p>
          </>
        ) : (
          <>
            <p className="font-medium text-slate-700">
              Glissez-déposez votre GeoTIFF ici
            </p>
            <p className="mt-1 text-sm text-slate-500">
              ou cliquez pour parcourir — .tif / .tiff{maxBytes ? `, max ${formatBytes(maxBytes)}` : ''}
            </p>
          </>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".tif,.tiff,image/tiff"
        className="hidden"
        onChange={(e) => validateAndSet(e.target.files?.[0])}
      />
      {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
    </div>
  )
}
