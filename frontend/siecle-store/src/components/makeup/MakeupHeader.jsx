import { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCart } from '../../hooks/useCart'
import { brandConfig } from '../../config/brand'
import SearchOverlayInput from '../SearchOverlayInput'

const MAKEUP_BASE = '/maquillage'

const NAV = [
  { label: 'Accueil',      href: MAKEUP_BASE },
  { label: 'Boutique',     href: `${MAKEUP_BASE}/shop` },
  { label: 'Nouveautés',   href: `${MAKEUP_BASE}/shop?filter=new` },
  { label: 'Best-sellers', href: `${MAKEUP_BASE}/shop?filter=best-sellers` },
  { label: 'Teint',        href: `${MAKEUP_BASE}/shop?type=teint` },
  { label: 'Lèvres',       href: `${MAKEUP_BASE}/shop?type=levres` },
  { label: 'Yeux',         href: `${MAKEUP_BASE}/shop?type=yeux` },
  { label: 'Accessoires',  href: `${MAKEUP_BASE}/shop?type=accessoires` },
  { label: 'Contact',      href: `${MAKEUP_BASE}/contact` },
]

function LogoImage() {
  const [failed, setFailed] = useState(false)
  if (failed) {
    return <span className="makeup-logo-fallback">{brandConfig.beauty.fallbackText}</span>
  }
  return (
    <img
      src={brandConfig.beauty.logo}
      alt={brandConfig.beauty.name}
      className="makeup-logo-img"
      onError={() => setFailed(true)}
    />
  )
}

export default function MakeupHeader() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const { items, setIsOpen }    = useCart()
  const totalItems              = items.reduce((s, i) => s + (i.qty || 1), 0)
  const location                = useLocation()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => { setMenuOpen(false) }, [location])

  return (
    <>
      <header className={`makeup-header${scrolled ? ' scrolled' : ''}`}>
        <div className="makeup-header-inner">

          {/* Logo LUNEA */}
          <Link to={MAKEUP_BASE} className="makeup-logo" aria-label={brandConfig.beauty.name}>
            <LogoImage />
          </Link>

          {/* Desktop nav */}
          <nav className="makeup-header-nav">
            {NAV.map(({ label, href }) => (
              <Link
                key={href}
                to={href}
                className={location.pathname === href ? 'active' : ''}
              >
                {label}
              </Link>
            ))}
          </nav>

          {/* Icons */}
          <div className="makeup-header-icons">
            <SearchOverlayInput theme="dark" />
            <Link to="/compte" className="makeup-header-icon-btn" aria-label="Mon compte">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
              </svg>
            </Link>
            <button
              className="makeup-header-icon-btn makeup-cart-badge"
              onClick={() => setIsOpen(true)}
              aria-label="Panier"
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
                <line x1="3" y1="6" x2="21" y2="6" /><path d="M16 10a4 4 0 0 1-8 0" />
              </svg>
              {totalItems > 0 && <span className="makeup-cart-count">{totalItems}</span>}
            </button>
            <button className="makeup-hamburger" onClick={() => setMenuOpen(true)} aria-label="Menu">
              <span /><span /><span />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile overlay */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            className="makeup-mobile-nav"
            initial={{ opacity: 0, x: '100%' }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: '100%' }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          >
            <button className="makeup-mobile-close" onClick={() => setMenuOpen(false)}>×</button>
            <div className="makeup-mobile-brand">
              <LogoImage />
            </div>
            {NAV.map(({ label, href }) => (
              <Link key={href} to={href}>{label}</Link>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
