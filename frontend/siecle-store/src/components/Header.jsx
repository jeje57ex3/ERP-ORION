import { useState, useEffect, lazy, Suspense } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCart } from '../hooks/useCart'

const PremiumSearchExperience = lazy(() => import('./search/PremiumSearchExperience'))

const MAKEUP_SITE_URL = '/maquillage'

/* Les quatre univers numerotes, dans l'ordre du site de reference, puis
   les destinations secondaires. « ACCUEIL » disparait : le logo y mene,
   comme sur la reference. */
const NAV_LINKS = [
  {
    to: '/vetements', label: 'VÊTEMENTS', num: '01',
    sub: [
      { label: 'Streetwear',        to: '/vetements' },
      { label: 'BACKCOURT 86',      to: '/boutique?category=backcourt-86' },
      { label: 'Costumes italiens', to: '/vetements?categorie=tailleur' },
    ],
  },
  { to: '/montres',       label: 'MONTRES',     num: '02' },
  { to: '/boutique?category=accessoires', label: 'ACCESSOIRES', num: '03' },
  { to: MAKEUP_SITE_URL,  label: 'LUNEA',       num: '04', newTab: true },
  { to: '/maison-siecle', label: 'MAISON' },
  { to: '/packs',         label: 'PACKS' },
  { to: '/drops',         label: 'DROPS' },
  { to: '/communaute',    label: 'COMMUNAUTÉ' },
]

/* Le numero d'univers, en petites capitales sourdes devant l'intitule. */
const Num = ({ children }) => children
  ? <span style={{ fontSize: 8, letterSpacing: '0.18em', color: 'var(--siecle-muted)', marginRight: 6, verticalAlign: 'super' }}>{children}</span>
  : null

export default function Header() {
  const [scrolled, setScrolled]     = useState(false)
  const [menuOpen, setMenuOpen]     = useState(false)
  const [sousMenu, setSousMenu]     = useState(null)
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
      background: scrolled ? 'rgba(9,9,9,0.96)' : 'transparent',
      backdropFilter: scrolled ? 'blur(12px)' : 'none',
      borderBottom: scrolled ? '1px solid var(--siecle-border)' : '1px solid transparent',
      transition: 'all 0.3s ease',
    },
    inner: {
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      width: '100%', maxWidth: 1440, margin: '0 auto',
    },
    logo: {
      fontFamily: 'var(--font-heading)',
      fontSize: 22, fontWeight: 700, letterSpacing: '0.18em',
      color: 'var(--siecle-white)',
    },
    nav: {
      display: 'flex', gap: 32, alignItems: 'center',
    },
    navLink: (active) => ({
      fontSize: 11, fontWeight: 600, letterSpacing: '0.14em',
      color: active ? 'var(--siecle-beige)' : 'var(--siecle-white)',
      transition: 'color 0.2s',
    }),
    right: {
      display: 'flex', gap: 16, alignItems: 'center',
    },
    cartBtn: {
      position: 'relative', cursor: 'pointer', background: 'none', border: 'none',
      color: 'var(--siecle-white)', fontSize: 18, padding: 4,
    },
    cartBadge: {
      position: 'absolute', top: -4, right: -4,
      width: 16, height: 16, borderRadius: '50%',
      background: 'var(--siecle-beige)', color: 'var(--siecle-black)',
      fontSize: 10, fontWeight: 700,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    },
    hamburger: {
      display: 'none', flexDirection: 'column', gap: 5, cursor: 'pointer',
      background: 'none', border: 'none', padding: 4,
    },
    bar: { width: 22, height: 1.5, background: 'var(--siecle-white)', transition: 'all 0.2s' },
  }

  return (
    <>
      <header style={s.header}>
        <div style={s.inner}>
          {/* Logo */}
          <Link to="/" style={s.logo}>SIÈCLE</Link>

          {/* Desktop nav */}
          <nav style={{ ...s.nav, ['@media(max-width:768px)']: { display: 'none' } }} className="siecle-desktop-nav">
            {NAV_LINKS.map(({ to, label, newTab, num, sub }) => (
              <div
                key={to}
                style={{ position: 'relative' }}
                onMouseEnter={() => setSousMenu(sub ? to : null)}
                onMouseLeave={() => setSousMenu(null)}
                onFocus={() => setSousMenu(sub ? to : null)}
                onBlur={e => {
                  // Ne refermer que lorsque le focus quitte VRAIMENT le
                  // groupe : sans ce test, passer d'un lien du sous-menu au
                  // suivant le ferait a chaque tabulation.
                  if (!e.currentTarget.contains(e.relatedTarget)) setSousMenu(null)
                }}
              >
                {newTab
                  ? <a href={to} target="_blank" rel="noopener noreferrer"
                      style={s.navLink(false)}
                      onMouseEnter={e => { e.currentTarget.style.color = 'var(--siecle-beige)' }}
                      onMouseLeave={e => { e.currentTarget.style.color = 'var(--siecle-white)' }}
                    >
                      <Num>{num}</Num>{label}
                    </a>
                  : <NavLink to={to}
                      style={({ isActive }) => s.navLink(isActive)}
                      onMouseEnter={e => e.currentTarget.style.color = 'var(--siecle-beige)'}
                      onMouseLeave={e => { if (!e.currentTarget.classList.contains('active')) e.currentTarget.style.color = 'var(--siecle-white)' }}
                    >
                      <Num>{num}</Num>{label}
                    </NavLink>
                }

                {sub && sousMenu === to && (
                  <div style={{
                    position: 'absolute', top: '100%', left: -18,
                    marginTop: 10, minWidth: 210, padding: '14px 0',
                    background: 'rgba(9,9,9,0.98)',
                    backdropFilter: 'blur(12px)',
                    border: '1px solid var(--siecle-border)',
                    display: 'flex', flexDirection: 'column',
                  }}>
                    {sub.map(e => (
                      <Link
                        key={e.to + e.label}
                        to={e.to}
                        onClick={() => setSousMenu(null)}
                        style={{
                          display: 'flex', alignItems: 'center',
                          justifyContent: 'space-between', gap: 16,
                          padding: '9px 18px',
                          fontSize: 11, fontWeight: 600, letterSpacing: '0.12em',
                          color: 'var(--siecle-white)',
                        }}
                        onMouseEnter={ev => { ev.currentTarget.style.color = 'var(--siecle-beige)' }}
                        onMouseLeave={ev => { ev.currentTarget.style.color = 'var(--siecle-white)' }}
                      >
                        {e.label}<span aria-hidden="true">↗</span>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </nav>

          {/* Right icons */}
          <div style={s.right}>
            <button onClick={() => setSearchOpen(true)} style={{ background: 'none', border: 'none', color: 'var(--siecle-white)', fontSize: 18, cursor: 'pointer', padding: 4 }} aria-label="Rechercher">🔍</button>
            <Link to="/compte" style={{ color: 'var(--siecle-white)', fontSize: 18, textDecoration: 'none' }} aria-label="Compte">👤</Link>
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
              position: 'fixed', inset: 0, background: 'var(--siecle-black)',
              zIndex: 999, display: 'flex', flexDirection: 'column',
              justifyContent: 'center', padding: '0 32px',
              gap: 32,
            }}
          >
            <button
              onClick={() => setMenuOpen(false)}
              style={{ position: 'absolute', top: 20, right: 24, background: 'none', border: 'none', color: 'var(--siecle-white)', fontSize: 24 }}
            >×</button>
            {NAV_LINKS.map(({ to, label, newTab, num, sub }, i) => (
              <motion.div
                key={to}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0, transition: { delay: i * 0.06 } }}
              >
                {newTab
                  ? <a href={to} target="_blank" rel="noopener noreferrer" onClick={() => setMenuOpen(false)}
                      style={{ fontFamily: 'var(--font-heading)', fontSize: 32, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--siecle-beige)', textTransform: 'uppercase' }}>
                      <Num>{num}</Num>{label} ↗
                    </a>
                  : <Link to={to} onClick={() => setMenuOpen(false)}
                      style={{ fontFamily: 'var(--font-heading)', fontSize: 32, fontWeight: 700, letterSpacing: '0.06em', color: 'var(--siecle-white)', textTransform: 'uppercase' }}>
                      <Num>{num}</Num>{label}
                    </Link>
                }
                {sub && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10, paddingLeft: 2 }}>
                    {sub.map(e => (
                      <Link key={e.to + e.label} to={e.to} onClick={() => setMenuOpen(false)}
                        style={{ fontSize: 13, letterSpacing: '0.12em', color: 'var(--siecle-muted-soft)', textTransform: 'uppercase' }}>
                        {e.label}
                      </Link>
                    ))}
                  </div>
                )}
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
