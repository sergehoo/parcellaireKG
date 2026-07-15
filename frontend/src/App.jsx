import { HashRouter, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { ToastProvider } from './components/Toasts'
import OrthophotoList from './pages/OrthophotoList'
import OrthophotoUpload from './pages/OrthophotoUpload'
import OrthophotoDetail from './pages/OrthophotoDetail'
import { ensureCsrf } from './api/client'

// Pose le cookie csrftoken dès le chargement de l'app.
ensureCsrf()

// HashRouter : aucune config serveur nécessaire, l'app est servie par
// Django sur /app/orthophotos/ et le routage se fait après le `#`.
export default function App() {
  return (
    <ToastProvider>
      <HashRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<OrthophotoList />} />
            <Route path="/upload" element={<OrthophotoUpload />} />
            <Route path="/orthophotos/:id" element={<OrthophotoDetail />} />
          </Route>
        </Routes>
      </HashRouter>
    </ToastProvider>
  )
}
