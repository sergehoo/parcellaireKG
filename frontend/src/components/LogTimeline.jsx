import { formatTime } from '../lib/format'

const LEVEL_STYLES = {
  INFO: 'bg-slate-400',
  WARNING: 'bg-amber-500',
  ERROR: 'bg-rose-500',
}

export default function LogTimeline({ logs }) {
  if (!logs || logs.length === 0) {
    return <p className="py-6 text-center text-sm text-slate-500">Aucun log pour le moment.</p>
  }
  return (
    <ol className="space-y-3">
      {logs.map((log, index) => (
        <li key={log.id ?? index} className="flex gap-3">
          <div className="flex flex-col items-center">
            <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${LEVEL_STYLES[log.level] || LEVEL_STYLES.INFO}`} />
            {index < logs.length - 1 && <span className="w-px flex-1 bg-slate-200" />}
          </div>
          <div className="min-w-0 flex-1 pb-1">
            <div className="flex items-baseline gap-2">
              <span className="text-xs tabular-nums text-slate-400">{formatTime(log.created_at)}</span>
              {log.level !== 'INFO' && (
                <span className={`text-xs font-semibold ${log.level === 'ERROR' ? 'text-rose-600' : 'text-amber-600'}`}>
                  {log.level}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-700">{log.message}</p>
            {log.command && (
              <pre className="mt-1 overflow-x-auto rounded bg-slate-900 px-2 py-1.5 text-xs text-slate-200">
                $ {log.command}
              </pre>
            )}
          </div>
        </li>
      ))}
    </ol>
  )
}
