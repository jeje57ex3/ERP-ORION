import { useState, useEffect, lazy, Suspense } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCart } from '../hooks/useCart'

const PremiumSearchExperience = lazy(() => import('./search/PremiumSearchExperience'))

const MAKEUP_SITE_URL = '/maquillage'

const NAV_LINKS = [
  { to: '/',              label: 'ACCUEIL' },
  { to: '/maison-siecle', label: 'MAISON' },
  { to: '/vetements',     label: 'VÊTEMENTS' },
  { to: '/montres',       label: 'MONTRES' },
  { to: MAKEUP_SITE_URL,  label: 'MAQUILLAGE', newTab: true },
  { to: '/packs',         label: 'PACKS' },
  { to: '/drops',         label: 'DROPS' },
  { to: '/communaute',    label: 'COMMUNAUTÉ' },
]

export default function Header() {
  const [scrolled, setScrolled]     = useState(false)
  const [menuOpen, setMenuOpen]     = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const { count, setIsOpen }        = useCart()
  const navigate                    = useNavigate()

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const s = {
    header: {
      position: 'fixed', top: 0, left: 0, right: 0, zIndex: 1000,
      height: 'var(--header-h)',
      display: 'flex', alignItems: 'center',
      padding: '0 24px',
      background: scrolled ? 'rgba(0,0,0,0.96)' : 'transparent',
      backdropFilter: scrolled ? 'blur(12px)' : 'none',
      borderBottom: scrolled ? '1px solid rgba(255,255,255,0.06)' : '1px solid transparent',
      transition: 'all 0.3s ease',
    },
    inner: {
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      width: '100%', maxWidth: 1440, margin: '0 auto',
    },
    logo: {
      fontFamily: 'Montserrat, sans-serif',
      fontSize: 22, fontWeight: 900, letterSpacing: '0.18em',
      color: '#fff',
    },
    nav: {
      display: 'flex', gap: 32, alignItems: 'center',
    },
    navLink: (active) => ({
      fontSize: 11, fontWeight: 700, letterSpacing: '0.14em',
      color: active ? 'var(--siecle-beige)' : '#fff',
      transition: 'color 0.2s',
    }),
    right: {
      display: 'flex', gap: 16, alignItems: 'center',
    },
    cartBtn: {
      position: 'relative', cursor: 'pointer', background: 'none', border: 'none',
      color: '#fff', fontSize: 18, padding: 4,
    },
    cartBadge: {
      position: 'absolute', top: -4, right: -4,
      width: 16, height: 16, borderRadius: '50%',
      background: 'var(--siecle-beige)', color: '#000',
      fontSize: 10, fontWeight: 800,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    },
    hamburger: {
      display: 'none', flexDirection: 'column', gap: 5, cursor: 'pointer',
      background: 'none', border: 'none', padding: 4,
    },
    bar: { width: 22, height: 1.5, background: '#fff', transition: 'all 0.2s' },
  }

  return (
    <>
      <header style={s.header}>
        <div style={s.inner}>
          {/* Logo */}
          <Link to="/" style={s.logo}>SIÈCLE</Link>

          {/* Desktop nav */}
          <nav style={{ ...s.nav, ['@media(max-width:768px)']: { display: 'none' } }} className="siecle-desktop-nav">
            {NAV_LINKS.map(({ to, label, newTab }) => (
              newTab
                ? <a key={to} href={to} target="_blank" rel="noopener noreferrer"
                    style={s.navLink(false)}
                    onMouseEnter={e => { e.currentTarget.style.color = 'var(--siecle-beige)' }}
                    onMouseLeave={e => { e.currentTarget.style.color = '#fff' }}
                  >
                    {label}
                  </a>
                : <NavLink key={to} to={to}
                    style={({ isActive }) => s.navLink(isActive)}
                    onMouseEnter={e => e.currentTarget.style.color = 'var(--siecle-beige)'}
                    onMouseLeave={e => { if (!e.currentTarget.closest('a')?.classList?.contains('active')) e.currentTarget.style.color = '#fff' }}
                  >
                    {label}
                  </NavLink>
            ))}
          </nav>

          {/* Right icons */}
          <div style={s.right}>
            <button onClick={() => setSearchOpen(true)} style={{ background: 'none', border: 'none', color: '#fff', fontSize: 18, cursor: 'pointer', padding: 4 }} aria-label="Rechercher">🔍</button>
            <Link to="/compte" style={{ color: '#fff', fontSize: 18, textDecoration: 'none' }} aria-label="Compte">👤</Link>
            <button style={s.cartBtn} onClick={() => setIsOpen(true)} aria-label="Panier">
              🛒
              {count > 0 && <span style={s.cartBadge}>{count}</span>}
            </button>
            <button
              style={{ ...s.hamburger, display: 'flex' }}
              className="siecle-hamburger"
              onClick={() => setMenuOpen(v => !v)}
              aria-label="Menu"
            >
              <span style={s.bar} />
              <span style={{ ...s.bar, width: menuOpen ? 22 : 14 }} />
              <span style={s.bar} />
            </button>
          </div>
        </div>
      </header>

      {/* Mobile menu */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, x: '100%' }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: '100%' }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            style={{
              position: 'fixed', inset: 0, background: '#000',
              zIndex: 999, display: 'flex', flexDirection: 'column',
              justifyContent: 'center', padding: '0 32px',
              gap: 32,
            }}
          >
            <button
              onClick={() => setMenuOpen(false)}
              style={{ position: 'absolute', top: 20, right: 24, background: 'none', border: 'none', color: '#fff', fontSize: 24 }}
            >×</button>
            {NAV_LINKS.map(({ to, label, newTab }, i) => (
              <motion.div
                key={to}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0, transition: { delay: i * 0.06 } }}
              >
                {newTab
                  ? <a href={to} target="_blank" rel="noopener noreferrer" onClick={() => setMenuOpen(false)}
                      style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 32, fontWeight: 900, letterSpacing: '0.06em', color: 'var(--siecle-beige)', textTransform: 'uppercase' }}>
                      {label} ↗
                    </a>
                  : <Link to={to} onClick={() => setMenuOpen(false)}
                      style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 32, fontWeight: 900, letterSpacing: '0.06em', color: '#fff', textTransform: 'uppercase' }}>
                      {label}
                    </Link>
                }
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {searchOpen && (
        <Suspense fallback={null}>
          <PremiumSearchExperience onClose={() => setSearchOpen(false)} />
        </Suspense>
      )}

      <style>{`
        .siecle-desktop-nav { display: flex; }
        .siecle-hamburger { display: none !important; }
        @media (max-width: 768px) {
          .siecle-desktop-nav { display: none !important; }
          .siecle-hamburger { display: flex !important; }
        }
      `}</style>
    </>
  )
}
