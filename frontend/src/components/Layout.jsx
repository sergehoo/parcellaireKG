import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { getAlertSummary } from '../api/analytics'

const NAV = [
  { to: '/', label: 'Carte', end: true },
  { to: '/dashboard', label: 'Tableau de bord' },
  { to: '/notifications', label: 'Notifications' },
  { to: '/r/projects', label: 'Projets' },
  { to: '/r/programs', label: 'Programmes' },
  { to: '/r/parcels', label: 'Parcelles' },
  { to: '/r/customers', label: 'Clients' },
  { to: '/r/leads', label: 'Prospects' },
  { to: '/r/reservations', label: 'Réservations' },
  { to: '/r/sales', label: 'Ventes' },
  { to: '/r/payments', label: 'Paiements' },
  { to: '/orthophotos', label: 'Orthophotos' },
]

const navClass = ({ isActive }) =>
  `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${
    isActive ? 'bg-orange-50 text-orange-700' : 'text-slate-600 hover:bg-slate-50'
  }`

// Compteur d'alertes critiques actives, rafraîchi par sondage léger (60 s).
// Local au Layout : le badge n'est consommé que dans la nav — pas besoin
// d'un store global. Garde d'égalité pour éviter les re-rendus inutiles.
function useCriticalCount() {
  const [count, setCount] = useState(0)
  const ctrlRef = useRef(null)

  useEffect(() => {
    let stopped = false
    const load = () => {
      ctrlRef.current?.abort()
      const ctrl = new AbortController()
      ctrlRef.current = ctrl
      getAlertSummary({ signal: ctrl.signal })
        .then((d) => {
          if (stopped) return
          const next = d?.critique ?? 0
          setCount((prev) => (prev === next ? prev : next))
        })
        .catch((err) => { if (err.name !== 'AbortError') { /* silencieux */ } })
    }
    load()
    const id = setInterval(load, 60000)
    return () => { stopped = true; clearInterval(id); ctrlRef.current?.abort() }
  }, [])

  return count
}

export default function Layout() {
  const criticalCount = useCriticalCount()

  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      <header className="sticky top-0 z-[700] border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] items-center gap-4 px-4 py-2.5 sm:px-6">
          <Link to="/" className="flex shrink-0 items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white"
              style={{ background: 'var(--kaydan)' }}>K</span>
            <span className="hidden text-lg font-semibold text-slate-900 sm:block">parcelaireKG</span>
          </Link>
          <nav className="flex items-center gap-1 overflow-x-auto">
            {NAV.map((n) => {
              const isNotif = n.to === '/notifications'
              return (
                <NavLink key={n.to} to={n.to} end={n.end} className={navClass}>
                  {n.label}
                  {isNotif && criticalCount > 0 && (
                    // Pastille visuelle uniquement — masquée aux lecteurs d'écran
                    // (le sens est porté par la région live ci-dessous).
                    <span
                      aria-hidden="true"
                      title={`${criticalCount} alerte(s) critique(s) active(s)`}
                      className="ml-1.5 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-rose-600 px-1.5 py-0.5 text-xs font-semibold text-white">
                      {criticalCount > 99 ? '99+' : criticalCount}
                    </span>
                  )}
                  {isNotif && (
                    // Toujours présente (même vide) pour que aria-live annonce
                    // les changements de compteur pendant le sondage.
                    <span className="sr-only" aria-live="polite">
                      {criticalCount > 0 ? ` — ${criticalCount} alertes critiques actives` : ''}
                    </span>
                  )}
                </NavLink>
              )
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
