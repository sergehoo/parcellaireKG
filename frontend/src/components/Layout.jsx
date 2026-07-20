import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { getAlertSummary } from '../api/analytics'
import { getMe, logout } from '../api/auth'
import { getTheme, setTheme } from '../lib/theme'

// Navigation groupée : la carte en accès direct, le reste réparti en menus
// déroulants thématiques.
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
const itemClass = ({ isActive }) => `flex items-center justify-between gap-2 px-3.5 py-2 text-sm ${
  isActive ? 'bg-orange-50 font-medium text-orange-700' : 'text-slate-700 hover:bg-slate-50'
}`

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

function Chevron({ open }) {
  return (
    <svg className={`h-3.5 w-3.5 transition-transform ${open ? 'rotate-180' : ''}`} viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 1 1 1.08 1.04l-4.25 4.5a.75.75 0 0 1-1.08 0l-4.25-4.5a.75.75 0 0 1 .02-1.06z" clipRule="evenodd" />
    </svg>
  )
}

// Ferme un menu au clic extérieur / Échap.
function useDismiss(open, onClose) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose() }
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey) }
  }, [open, onClose])
  return ref
}

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
        .then((d) => { if (!stopped) setCount((prev) => { const n = d?.critique ?? 0; return prev === n ? prev : n }) })
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
  const ref = useDismiss(open, onClose)
  const active = group.items.some((it) => isPathActive(location.pathname, it.to))
  const groupBadge = group.items.some((it) => it.notif) ? criticalCount : 0
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={onToggle} aria-haspopup="true" aria-expanded={open}
        className={`flex items-center gap-1 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${
          active || open ? 'bg-orange-50 text-orange-700' : 'text-slate-600 hover:bg-slate-50'
        }`}>
        {group.label}<Badge count={groupBadge} /><Chevron open={open} />
      </button>
      {open && (
        <div className="absolute left-0 top-full z-[720] mt-1 min-w-[13rem] overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
          {group.items.map((it) => (
            <NavLink key={it.to} to={it.to} onClick={onClose} className={itemClass}>
              <span>{it.label}</span>{it.notif && <Badge count={criticalCount} />}
            </NavLink>
          ))}
        </div>
      )}
    </div>
  )
}

function UserMenu({ me, open, onToggle, onClose }) {
  const ref = useDismiss(open, onClose)
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={onToggle} aria-haspopup="true" aria-expanded={open}
        className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 hover:bg-slate-50">
        <span className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold text-white"
          style={{ background: 'var(--kaydan)' }}>{me?.initials || '…'}</span>
        <span className="hidden max-w-[9rem] truncate text-sm font-medium text-slate-700 sm:block">
          {me?.full_name || 'Compte'}
        </span>
        <Chevron open={open} />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-[720] mt-1 min-w-[15rem] overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
          <div className="border-b border-slate-100 px-3.5 py-2.5">
            <div className="truncate text-sm font-semibold text-slate-800">{me?.full_name || '—'}</div>
            <div className="truncate text-xs text-slate-500">{me?.email || me?.username || ''}</div>
          </div>
          <NavLink to="/profile" onClick={onClose} className={itemClass}><span>Mon profil</span></NavLink>
          <a href="/accounts/password/change/" className="block px-3.5 py-2 text-sm text-slate-700 hover:bg-slate-50">
            Changer le mot de passe
          </a>
          {me?.is_staff && (
            <a href="/admin/" className="block px-3.5 py-2 text-sm text-slate-700 hover:bg-slate-50">Administration</a>
          )}
          <button type="button" onClick={logout}
            className="block w-full border-t border-slate-100 px-3.5 py-2 text-left text-sm font-medium text-rose-600 hover:bg-rose-50">
            Déconnexion
          </button>
        </div>
      )}
    </div>
  )
}

function ThemeToggle({ theme, onToggle }) {
  const dark = theme === 'dark'
  return (
    <button type="button" onClick={onToggle}
      title={dark ? 'Passer en clair' : 'Passer en sombre'}
      aria-label={dark ? 'Activer le thème clair' : 'Activer le thème sombre'}
      className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-50">
      {dark ? (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  )
}

export default function Layout() {
  const criticalCount = useCriticalCount()
  const [openMenu, setOpenMenu] = useState(null)
  const [me, setMe] = useState(null)
  const [theme, setThemeState] = useState(getTheme())

  useEffect(() => {
    const c = new AbortController()
    getMe({ signal: c.signal }).then(setMe).catch(() => {})
    return () => c.abort()
  }, [])

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    setThemeState(next)
  }

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
                open={openMenu === g.label}
                onToggle={() => setOpenMenu((cur) => (cur === g.label ? null : g.label))}
                onClose={() => setOpenMenu(null)}
                criticalCount={criticalCount} />
            ))}
          </nav>

          <div className="ml-auto flex shrink-0 items-center gap-1">
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
            <UserMenu me={me}
              open={openMenu === '__user__'}
              onToggle={() => setOpenMenu((cur) => (cur === '__user__' ? null : '__user__'))}
              onClose={() => setOpenMenu(null)} />
          </div>

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
