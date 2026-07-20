import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { getAlertSummary } from '../api/analytics'

// Navigation groupée : la carte en accès direct, le reste réparti en menus
// déroulants thématiques (le menu à plat était devenu trop long).
const CARTE = { to: '/', label: 'Carte', end: true }
const GROUPS = [
  { label: 'Pilotage', items: [
    { to: '/dashboard', label: 'Tableau de bord' },
    { to: '/notifications', label: 'Notifications', notif: true },
  ] },
  { label: 'Patrimoine', items: [
    { to: '/r/projects', label: 'Projets' },
    { to: '/r/programs', label: 'Programmes' },
    { to: '/r/parcels', label: 'Parcelles' },
    { to: '/r/blocks', label: 'Îlots' },
    { to: '/r/phases', label: 'Phases' },
    { to: '/r/assets', label: 'Actifs' },
  ] },
  { label: 'Commercial', items: [
    { to: '/r/customers', label: 'Clients' },
    { to: '/r/leads', label: 'Prospects' },
    { to: '/r/reservations', label: 'Réservations' },
    { to: '/r/sales', label: 'Ventes' },
    { to: '/r/payments', label: 'Paiements' },
  ] },
  { label: 'Technique', items: [
    { to: '/r/construction', label: 'Chantiers' },
    { to: '/r/datasets', label: 'Jeux de données' },
    { to: '/orthophotos', label: 'Orthophotos' },
  ] },
]

const isPathActive = (pathname, to) => pathname === to || pathname.startsWith(to + '/')

function Badge({ count }) {
  if (!count) return null
  return (
    <span aria-hidden="true"
      title={`${count} alerte(s) critique(s) active(s)`}
      className="ml-1.5 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-rose-600 px-1.5 py-0.5 text-xs font-semibold text-white">
      {count > 99 ? '99+' : count}
    </span>
  )
}

// Compteur d'alertes critiques actives, rafraîchi par sondage léger (60 s).
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

function NavGroup({ group, open, onToggle, onClose, criticalCount }) {
  const location = useLocation()
  const ref = useRef(null)
  const active = group.items.some((it) => isPathActive(location.pathname, it.to))
  const groupBadge = group.items.some((it) => it.notif) ? criticalCount : 0

  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose() }
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open, onClose])

  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={onToggle}
        aria-haspopup="true" aria-expanded={open}
        className={`flex items-center gap-1 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${
          active || open ? 'bg-orange-50 text-orange-700' : 'text-slate-600 hover:bg-slate-50'
        }`}>
        {group.label}
        <Badge count={groupBadge} />
        <svg className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06z" clipRule="evenodd" />
        </svg>
      </button>
      {open && (
        <div className="absolute left-0 top-full z-[720] mt-1 min-w-[13rem] overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
          {group.items.map((it) => (
            <NavLink key={it.to} to={it.to} onClick={onClose}
              className={({ isActive }) => `flex items-center justify-between gap-2 px-3.5 py-2 text-sm ${
                isActive ? 'bg-orange-50 font-medium text-orange-700' : 'text-slate-700 hover:bg-slate-50'
              }`}>
              <span>{it.label}</span>
              {it.notif && <Badge count={criticalCount} />}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Layout() {
  const criticalCount = useCriticalCount()
  const [openGroup, setOpenGroup] = useState(null)

  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      <header className="sticky top-0 z-[700] border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-4 py-2.5 sm:px-6">
          <Link to="/" className="flex shrink-0 items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-bold text-white"
              style={{ background: 'var(--kaydan)' }}>K</span>
            <span className="hidden text-lg font-semibold text-slate-900 sm:block">parcelaireKG</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-1">
            <NavLink to={CARTE.to} end={CARTE.end}
              className={({ isActive }) => `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${
                isActive ? 'bg-orange-50 text-orange-700' : 'text-slate-600 hover:bg-slate-50'
              }`}>
              {CARTE.label}
            </NavLink>
            {GROUPS.map((g) => (
              <NavGroup key={g.label} group={g}
                open={openGroup === g.label}
                onToggle={() => setOpenGroup((cur) => (cur === g.label ? null : g.label))}
                onClose={() => setOpenGroup(null)}
                criticalCount={criticalCount} />
            ))}
          </nav>
          {/* Annonce accessible du nombre d'alertes critiques (région live). */}
          <span className="sr-only" aria-live="polite">
            {criticalCount > 0 ? `${criticalCount} alertes critiques actives` : ''}
          </span>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
