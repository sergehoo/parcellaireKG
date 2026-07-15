const STATUS_STYLES = {
  PENDING: 'bg-amber-100 text-amber-800 ring-amber-200',
  PROCESSING: 'bg-sky-100 text-sky-800 ring-sky-200',
  DONE: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  FAILED: 'bg-rose-100 text-rose-800 ring-rose-200',
}

export default function StatusBadge({ status, label }) {
  const style = STATUS_STYLES[status] || 'bg-slate-100 text-slate-700 ring-slate-200'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${style}`}>
      {status === 'PROCESSING' && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-500" />
      )}
      {label || status}
    </span>
  )
}
