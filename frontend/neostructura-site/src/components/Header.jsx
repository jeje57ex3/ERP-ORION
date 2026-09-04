import { useState, useEffect } from 'react'
import { NavLink, Link } from 'react-router-dom'
import { useTheme } from '../hooks/useTheme'

const NAV_LINKS = [
  { to: '/', label: 'Accueil', end: true },
  { to: '/nos-metiers', label: 'Nos métiers' },
  { to: '/configurateur', label: 'Configurateur' },
  { to: '/realisations', label: 'Réalisations' },
  { to: '/contact', label: 'Contact' },
]

export default function Header() {
  const { theme, toggleTheme } = useTheme()
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        height: 'var(--header-h)',
        display: 'flex', alignItems: 'center',
        background: scrolled ? 'var(--bg-elevated)' : 'transparent',
        borderBottom: scrolled ? '1px solid var(--border)' : '1px solid transparent',
        backdropFilter: scrolled ? 'blur(10px)' : 'none',
        transition: 'background .3s ease, border-color .3s ease',
      }}
    >
      <div className="neo-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10 }} onClick={() => setMenuOpen(false)}>
          <span style={{
            width: 34, height: 34, borderRadius: 8,
            background: 'var(--surface-brand)', color: 'var(--surface-brand-fg)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16,
          }}>N</span>
          <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 19, letterSpacing: '0.01em' }}>
            NÉOSTRUCTURA
          </span>
        </Link>

        <nav className="neo-nav-desktop" style={{ display: 'flex', alignItems: 'center', gap: 36 }}>
          {NAV_LINKS.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              style={({ isActive }) => ({
                fontSize: 14, fontWeight: 600,
                color: isActive ? 'var(--accent)' : 'var(--text)',
                opacity: isActive ? 1 : 0.82,
              })}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={toggleTheme}
            aria-label="Changer de thème"
            style={{
              width: 38, height: 38, borderRadius: '50%',
              border: '1px solid var(--border)', background: 'var(--bg-elevated)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16,
            }}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          <Link to="/configurateur" className="neo-btn neo-btn-primary neo-nav-cta">
            Démarrer mon projet
          </Link>
          <button
            className="neo-nav-toggle"
            onClick={() => setMenuOpen(v => !v)}
            aria-label="Menu"
            style={{
              display: 'none', width: 38, height: 38, border: '1px solid var(--border)',
              borderRadius: 8, background: 'var(--bg-elevated)', fontSize: 18,
            }}
          >
            {menuOpen ? '✕' : '☰'}
          </button>
        </div>
      </div>

      {menuOpen && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0,
          background: 'var(--bg-elevated)', borderBottom: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column', padding: '16px 24px', gap: 4,
        }} className="neo-nav-mobile-panel">
          {NAV_LINKS.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              onClick={() => setMenuOpen(false)}
              style={({ isActive }) => ({
                padding: '12px 4px', fontSize: 15, fontWeight: 600,
                color: isActive ? 'var(--accent)' : 'var(--text)',
                borderBottom: '1px solid var(--border)',
              })}
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      )}

      <style>{`
        @media (max-width: 860px) {
          .neo-nav-desktop { display: none !important; }
          .neo-nav-cta { display: none !important; }
          .neo-nav-toggle { display: flex !important; align-items: center; justify-content: center; }
        }
      `}</style>
    </header>
  )
}
