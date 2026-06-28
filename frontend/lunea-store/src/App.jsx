import { lazy, Suspense } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import LuneaHeader from './components/LuneaHeader'
import LuneaFooter from './components/LuneaFooter'

import LuneaHome            from './pages/LuneaHome'
import LuneaBoutique        from './pages/LuneaBoutique'
import LuneaSoins           from './pages/LuneaSoins'
import LuneaRituels         from './pages/LuneaRituels'
import LuneaMaquillage      from './pages/LuneaMaquillage'
import LuneaRituelDetail   from './pages/LuneaRituelDetail'
import LuneaProduitDetail  from './pages/LuneaProduitDetail'
import LuneaPanier          from './pages/LuneaPanier'
import LuneaCompte          from './pages/LuneaCompte'
import LuneaCommandes       from './pages/LuneaCommandes'
import LuneaFidelite        from './pages/LuneaFidelite'
import LuneaCheckoutSuccess from './pages/LuneaCheckoutSuccess'
import LuneaCheckoutCancel  from './pages/LuneaCheckoutCancel'
import LuneaResetPassword   from './pages/LuneaResetPassword'
import MentionsLegales from '../../shared/legal/pages/MentionsLegales'
import PolitiqueConfidentialite from '../../shared/legal/pages/PolitiqueConfidentialite'
import PolitiqueCookies from '../../shared/legal/pages/PolitiqueCookies'
import CGV from '../../shared/legal/pages/CGV'
import LivraisonRetours from '../../shared/legal/pages/LivraisonRetours'
import FAQ from '../../shared/legal/pages/FAQ'
import ContactPage from '../../shared/components/ContactPage'

const LuneaLogin          = lazy(() => import('./pages/LuneaLogin'))
const LuneaForgotPassword = lazy(() => import('./pages/LuneaForgotPassword'))

function Placeholder({ title }) {
  return (
    <div style={{ paddingTop: 'var(--header-h)', minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center', color: 'var(--color-text-muted)' }}>
        <p className="lunea-eyebrow">{title}</p>
        <p style={{ fontSize: 13, marginTop: 8 }}>Cette page sera bientôt disponible.</p>
      </div>
    </div>
  )
}

export default function App() {
  const location = useLocation()

  // Don't show header on auth pages
  const isAuthPage = location.pathname.includes('/login') || location.pathname.includes('/mot-de-passe') || location.pathname.includes('/reset-password')
  const isCheckoutStatusPage = location.pathname.includes('/checkout/success') || location.pathname.includes('/checkout/cancel')

  return (
    <>
      {!isAuthPage && !isCheckoutStatusPage && <LuneaHeader />}
      <Suspense fallback={<div style={{ paddingTop: 120, textAlign: 'center', color: 'var(--color-text-muted)' }}>Chargement...</div>}>
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            {/* Auth — standalone */}
            <Route path="lunea/login/"                element={<LuneaLogin />} />
            <Route path="lunea/mot-de-passe-oublie/"  element={<LuneaForgotPassword />} />
            <Route path="lunea/reset-password/:token" element={<LuneaResetPassword />} />

            {/* Checkout status — standalone */}
            <Route path="lunea/checkout/success/"     element={<LuneaCheckoutSuccess />} />
            <Route path="lunea/checkout/cancel/"      element={<LuneaCheckoutCancel />} />

            {/* Main routes */}
            <Route path="lunea/"                    element={<LuneaHome />} />
            <Route path="lunea/boutique/"            element={<LuneaBoutique />} />
            <Route path="lunea/soins/"               element={<LuneaSoins />} />
            <Route path="lunea/rituels/"             element={<LuneaRituels />} />
            <Route path="lunea/rituels/:slug/"       element={<LuneaRituelDetail />} />
            <Route path="lunea/produit/:slug/"       element={<LuneaProduitDetail />} />
            <Route path="lunea/maquillage/"          element={<LuneaMaquillage />} />
            <Route path="lunea/panier/"              element={<LuneaPanier />} />
            <Route path="lunea/compte/"              element={<LuneaCompte />} />
            <Route path="lunea/compte/commandes/"    element={<LuneaCommandes />} />
            <Route path="lunea/compte/fidelite/"     element={<LuneaFidelite />} />

            {/* Legal pages */}
            <Route path="lunea/mentions-legales/"   element={<MentionsLegales brand="lunea" />} />
            <Route path="lunea/confidentialite/"    element={<PolitiqueConfidentialite brand="lunea" />} />
            <Route path="lunea/cookies/"            element={<PolitiqueCookies brand="lunea" />} />
            <Route path="lunea/cgv/"               element={<CGV brand="lunea" />} />
            <Route path="lunea/livraison-retours/"  element={<LivraisonRetours brand="lunea" />} />
            <Route path="lunea/faq/"               element={<FAQ brand="lunea" />} />
            <Route path="lunea/contact/"           element={<ContactPage brand="lunea" />} />

            {/* Fallback */}
            <Route path="*" element={<LuneaHome />} />
          </Routes>
        </AnimatePresence>
      </Suspense>
      {!isAuthPage && !isCheckoutStatusPage && <LuneaFooter />}
    </>
  )
}
