import { Link, NavLink, Outlet } from 'react-router-dom'

export default function Layout() {
  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-600 text-sm font-bold text-white">
                O
              </span>
              <span className="text-lg font-semibold text-slate-900">Orthophotos</span>
            </Link>
            <nav className="flex items-center gap-1">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm font-medium ${
                    isActive ? 'bg-sky-50 text-sky-700' : 'text-slate-600 hover:bg-slate-50'
                  }`}
              >
                Liste
              </NavLink>
              <NavLink
                to="/upload"
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm font-medium ${
                    isActive ? 'bg-sky-50 text-sky-700' : 'text-slate-600 hover:bg-slate-50'
                  }`}
              >
                Nouvelle orthophoto
              </NavLink>
            </nav>
          </div>
          <a
            href="/"
            className="text-sm text-slate-500 hover:text-slate-700"
          >
            ← Retour au parcellaire
          </a>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
