import { HashRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { ToastProvider } from './components/Toasts'
import MapView from './pages/MapView'
import Dashboard from './pages/Dashboard'
import AtRiskPage from './pages/AtRiskPage'
import NotificationCenter from './pages/NotificationCenter'
import ResourceListPage from './pages/ResourceListPage'
import ResourceDetailPage from './pages/ResourceDetailPage'
import ResourceFormPage from './pages/ResourceFormPage'
import OrthophotoList from './pages/OrthophotoList'
import OrthophotoUpload from './pages/OrthophotoUpload'
import OrthophotoDetail from './pages/OrthophotoDetail'
import { ensureCsrf } from './api/client'

// Pose le cookie csrftoken dès le chargement de l'app.
ensureCsrf()

// HashRouter : le SPA est servi par Django sur /app/ (login requis) ;
// tout le routage se fait après le `#`. La carte est la vue d'accueil.
export default function App() {
  return (
    <ToastProvider>
      <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<MapView />} />
            <Route path="/carte" element={<MapView />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/pilotage/risques" element={<AtRiskPage />} />
            <Route path="/notifications" element={<NotificationCenter />} />

            {/* CRUD générique piloté par le registre config/resources.js */}
            <Route path="/r/:resource" element={<ResourceListPage />} />
            <Route path="/r/:resource/new" element={<ResourceFormPage />} />
            <Route path="/r/:resource/:id" element={<ResourceDetailPage />} />
            <Route path="/r/:resource/:id/edit" element={<ResourceFormPage />} />

            {/* Orthophotos (module dédié) */}
            <Route path="/orthophotos" element={<OrthophotoList />} />
            <Route path="/orthophotos/upload" element={<OrthophotoUpload />} />
            <Route path="/orthophotos/:id" element={<OrthophotoDetail />} />
            <Route path="/upload" element={<Navigate to="/orthophotos/upload" replace />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </HashRouter>
    </ToastProvider>
  )
}
