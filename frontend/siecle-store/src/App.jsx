import { useEffect, lazy, Suspense } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { CartProvider } from './hooks/useCart'
import { initAuthFromStorage } from './api/customer'
import Layout from './components/Layout'
import CustomerAccountLayout from './components/CustomerAccountLayout'
import LuxuryLoader from './components/LuxuryLoader'

// Shared
import ComingSoonPage from '../../shared/components/ComingSoonPage'
import MentionsLegales from '../../shared/legal/pages/MentionsLegales'
import PolitiqueConfidentialite from '../../shared/legal/pages/PolitiqueConfidentialite'
import PolitiqueCookies from '../../shared/legal/pages/PolitiqueCookies'
import CGV from '../../shared/legal/pages/CGV'
import LivraisonRetours from '../../shared/legal/pages/LivraisonRetours'
import FAQ from '../../shared/legal/pages/FAQ'
import ContactPage from '../../shared/components/ContactPage'

// Core pages (eager)
import LandingHome        from './pages/LandingHome'
import Shop               from './pages/Shop'
import ProductDetail      from './pages/ProductDetail'
import Cart               from './pages/Cart'
import CheckoutSuccess    from './pages/CheckoutSuccess'
import CheckoutCancel     from './pages/CheckoutCancel'
import ClothingHome       from './pages/ClothingHome'
import WatchesHome        from './pages/WatchesHome'
import MakeupHome         from './pages/MakeupHome'
import MakeupShop         from './pages/MakeupShop'
import MakeupContact      from './pages/MakeupContact'
import SearchResults      from './pages/SearchResults'
import CartToast          from './components/CartToast'
import Login              from './pages/Login'
import ForgotPassword     from './pages/ForgotPassword'
import ResetPassword      from './pages/ResetPassword'
import CustomerAccount    from './pages/CustomerAccount'
import CustomerOrders     from './pages/CustomerOrders'
import Rewards            from './pages/Rewards'
import Affiliate          from './pages/Affiliate'
import GiftCardRedeem     from './pages/GiftCardRedeem'
import WatchProductDetail from './pages/WatchProductDetail'

// Lazy-loaded feature pages
const WatchAtelierPage  = lazy(() => import('./pages/WatchAtelierPage'))
const MaisonSiecle      = lazy(() => import('./pages/MaisonSiecle'))
const ImmersiveUniverse = lazy(() => import('./pages/ImmersiveUniverse'))
const Checkout          = lazy(() => import('./pages/Checkout'))
const OrderSuccess      = lazy(() => import('./pages/OrderSuccess'))
const GiftCardAnimated  = lazy(() => import('./pages/GiftCardAnimated'))
const LookBuilder       = lazy(() => import('./pages/LookBuilder'))
const PremiumPacks      = lazy(() => import('./pages/PremiumPacks'))
const PrivateDrop       = lazy(() => import('./pages/PrivateDrop'))
const CommunityWall           = lazy(() => import('./pages/CommunityWall'))
const WatchCustomizerFullPage = lazy(() => import('./pages/WatchCustomizerFullPage'))
const IdentityQuiz      = lazy(() => import('./pages/IdentityQuiz'))
const CustomerPrivileges= lazy(() => import('./pages/CustomerPrivileges'))
const BeautyQuiz        = lazy(() => import('./pages/BeautyQuiz'))
const ShadeFinder       = lazy(() => import('./pages/ShadeFinder'))
const SizeGuide         = lazy(() => import('./pages/SizeGuide'))
const WatchCompare      = lazy(() => import('./pages/WatchCompare'))
const WatchCertificate  = lazy(() => import('./pages/WatchCertificate'))
const WatchGallery3D    = lazy(() => import('./pages/WatchGallery3D'))

const Fallback = () => <LuxuryLoader />

export default function App() {
  const location = useLocation()

  useEffect(() => { initAuthFromStorage() }, [])

  return (
    <CartProvider>
      <CartToast />
      <Suspense fallback={<Fallback />}>
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            {/* Auth */}
            <Route path="compte/connexion"           element={<Login mode="login" />} />
            <Route path="compte/inscription"         element={<Login mode="register" />} />
            <Route path="compte/mot-de-passe-oublie" element={<ForgotPassword />} />
            <Route path="reset-password/:token"      element={<ResetPassword />} />

            {/* ── SIÈCLE BEAUTY — univers maquillage standalone ── */}
            <Route path="maquillage"                        element={<MakeupHome />} />
            <Route path="maquillage/shop"                   element={<MakeupShop />} />
            <Route path="maquillage/contact"                element={<MakeupContact />} />
            <Route path="maquillage/quiz"                   element={<BeautyQuiz />} />
            <Route path="maquillage/trouver-ma-teinte"      element={<ShadeFinder />} />

            {/* Main layout */}
            <Route element={<Layout />}>
              <Route index                                    element={<LandingHome />} />
              <Route path="maison-siecle"                     element={<MaisonSiecle />} />
              <Route path="univers"                           element={<ImmersiveUniverse />} />
              <Route path="search"                            element={<SearchResults />} />
              <Route path="boutique"                          element={<Shop />} />
              <Route path="vetements"                         element={<ClothingHome />} />
              <Route path="montres"                             element={<WatchesHome />} />
              <Route path="montres/atelier"                   element={<WatchAtelierPage />} />
              <Route path="montres/personnaliser"             element={<WatchCustomizerFullPage />} />
              <Route path="montres/comparer"                  element={<WatchCompare />} />
              <Route path="montres/galerie-3d"                element={<WatchGallery3D />} />
              <Route path="montres/certificat/:id"            element={<WatchCertificate />} />
              <Route path="product/:slug"                     element={<ProductDetail />} />
              <Route path="montres/:slug"                     element={<WatchProductDetail />} />
              <Route path="cart"                              element={<Cart />} />
              <Route path="checkout"                          element={<Checkout />} />
              <Route path="checkout/success"                  element={<CheckoutSuccess />} />
              <Route path="checkout/cancel"                   element={<CheckoutCancel />} />
              <Route path="commande/success"                  element={<OrderSuccess />} />
              <Route path="carte-cadeau"                      element={<GiftCardAnimated />} />
              <Route path="creer-mon-look"                    element={<LookBuilder />} />
              <Route path="packs"                             element={<PremiumPacks />} />
              <Route path="drops"                             element={<PrivateDrop />} />
              <Route path="drop-prive"                        element={<PrivateDrop />} />
              <Route path="communaute"                          element={<CommunityWall />} />
              <Route path="creer-mon-identite-siecle"         element={<IdentityQuiz />} />
              <Route path="guide-taille"                      element={<SizeGuide />} />

              {/* Legal pages */}
              <Route path="mentions-legales"    element={<MentionsLegales brand="siecle" />} />
              <Route path="confidentialite"     element={<PolitiqueConfidentialite brand="siecle" />} />
              <Route path="cookies"             element={<PolitiqueCookies brand="siecle" />} />
              <Route path="cgv"                 element={<CGV brand="siecle" />} />
              <Route path="livraison-retours"   element={<LivraisonRetours brand="siecle" />} />
              <Route path="faq"                 element={<FAQ brand="siecle" />} />
              <Route path="contact"             element={<ContactPage brand="siecle" />} />

              {/* Customer account */}
              <Route path="compte" element={<CustomerAccountLayout />}>
                <Route index                                  element={<CustomerAccount />} />
                <Route path="commandes"                       element={<CustomerOrders />} />
                <Route path="fidelite"                        element={<Rewards />} />
                <Route path="parrainage"                      element={<Affiliate />} />
                <Route path="carte-cadeau"                    element={<GiftCardRedeem />} />
                <Route path="privileges"                      element={<CustomerPrivileges />} />
              </Route>
            </Route>
          </Routes>
        </AnimatePresence>
      </Suspense>
    </CartProvider>
  )
}
