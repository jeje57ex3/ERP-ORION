import { Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import Footer from './components/Footer'
import HomePage from './pages/HomePage'
import MetiersPage from './pages/MetiersPage'
import RealisationsPage from './pages/RealisationsPage'
import ConfigurateurPage from './pages/ConfigurateurPage'
import ContactPage from './pages/ContactPage'
import EspaceClientLoginPage from './pages/EspaceClientLoginPage'
import EspaceClientDashboardPage from './pages/EspaceClientDashboardPage'
import NotFoundPage from './pages/NotFoundPage'

export default function App() {
  return (
    <div style={{ background: 'var(--bg)', color: 'var(--text)', minHeight: '100vh' }}>
      <Header />
      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/nos-metiers" element={<MetiersPage />} />
          <Route path="/realisations" element={<RealisationsPage />} />
          <Route path="/configurateur" element={<ConfigurateurPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/espace-client/connexion" element={<EspaceClientLoginPage />} />
          <Route path="/espace-client" element={<EspaceClientDashboardPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}
