import { Link, NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Carte', end: true },
  { to: '/dashboard', label: 'Tableau de bord' },
  { to: '/notifications', label: 'Notifications' },
  { to: '/r/projects', label: 'Projets' },
  { to: '/r/programs', label: 'Programmes' },
  { to: '/r/parcels', label: 'Parcelles' },
  { to: '/r/customers', label: 'Clients' },
  { to: '/r/reservations', label: 'Réservations' },
  { to: '/r/sales', label: 'Ventes' },
  { to: '/r/payments', label: 'Paiements' },
  { to: '/orthophotos', label: 'Orthophotos' },
]

const navClass = ({ isActive }) =>
  `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${
    isActive ? 'bg-orange-50 text-orange-700' : 'text-slate-600 hover:bg-slate-50'
  }`

export default function Layout() {
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
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} className={navClass}>{n.label}</NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
