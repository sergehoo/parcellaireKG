import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { ToastProvider } from './components/Toasts'
import MapView from './pages/MapView'
import OrthophotoList from './pages/OrthophotoList'
import OrthophotoUpload from './pages/OrthophotoUpload'
import OrthophotoDetail from './pages/OrthophotoDetail'
import { ensureCsrf } from './api/client'

// Pose le cookie csrftoken dès le chargement de l'app.
ensureCsrf()

// HashRouter : le SPA est servi par Django sur /app/ (login requis) et
// tout le routage se fait après le `#`, sans réécriture serveur.
// La carte est la vue d'accueil ; /map et /map_commercial (Django)
// redirigent vers #/carte.
export default function App() {
  return (
    <ToastProvider>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<MapView />} />
            <Route path="/carte" element={<MapView />} />
            <Route path="/orthophotos" element={<OrthophotoList />} />
            <Route path="/orthophotos/upload" element={<OrthophotoUpload />} />
            <Route path="/orthophotos/:id" element={<OrthophotoDetail />} />
            {/* Rétrocompat : anciens liens du SPA orthophotos. */}
            <Route path="/upload" element={<Navigate to="/orthophotos/upload" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </HashRouter>
    </ToastProvider>
  )
}
