export default function ProgressBar({ percent, status, label }) {
  const clamped = Math.max(0, Math.min(100, percent || 0))
  const color = status === 'FAILED'
    ? 'bg-rose-500'
    : status === 'DONE'
      ? 'bg-emerald-500'
      : 'bg-sky-500'
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-slate-600">
        <span className="truncate">{label || ''}</span>
        <span className="ml-2 shrink-0 font-medium">{clamped}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  )
}
