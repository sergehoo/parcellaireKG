import { Link, NavLink, Outlet } from 'react-router-dom'

const navClass = ({ isActive }) =>
  `rounded-lg px-3 py-1.5 text-sm font-medium ${
    isActive ? 'bg-sky-50 text-sky-700' : 'text-slate-600 hover:bg-slate-50'
  }`

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-600 text-sm font-bold text-white">
                P
              </span>
              <span className="text-lg font-semibold text-slate-900">parcelaireKG</span>
            </Link>
            <nav className="flex items-center gap-1">
              <NavLink to="/" end className={navClass}>Carte</NavLink>
              <NavLink to="/orthophotos" className={navClass}>Orthophotos</NavLink>
            </nav>
          </div>
          {/* Le CRUD (projets, ventes, paiements…) reste sur Django pour
              l'instant : lien vers le tableau de bord historique. */}
          <a href="/" className="hidden text-sm text-slate-500 hover:text-slate-700 sm:block">
            Tableau de bord →
          </a>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
