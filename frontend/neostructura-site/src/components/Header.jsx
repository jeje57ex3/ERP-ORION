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
        height: scrolled ? 'var(--header-h-scrolled)' : 'var(--header-h)',
        display: 'flex', alignItems: 'center',
        background: scrolled ? 'var(--bg-elevated)' : 'transparent',
        borderBottom: scrolled ? '1px solid var(--border)' : '1px solid transparent',
        backdropFilter: scrolled ? 'blur(10px)' : 'none',
        transition: 'background .3s ease, border-color .3s ease, height .3s ease',
      }}
    >
      <div className="neo-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20, width: '100%' }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }} onClick={() => setMenuOpen(false)}>
          <span style={{
            width: 34, height: 34, borderRadius: 8, background: '#F7F7F4',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 4, flexShrink: 0,
          }}>
            <img src="/logo-icon.png" alt="NÉOSTRUCTURA" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          </span>
          <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 19, letterSpacing: '0.01em', whiteSpace: 'nowrap' }}>
            NÉOSTRUCTURA
          </span>
        </Link>

        <nav className="neo-nav-desktop" style={{ display: 'flex', alignItems: 'center', gap: 26, flexShrink: 0 }}>
          {NAV_LINKS.map(link => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.end}
              style={({ isActive }) => ({
                fontSize: 14, fontWeight: 600, whiteSpace: 'nowrap',
                color: isActive ? 'var(--accent)' : 'var(--text)',
                opacity: isActive ? 1 : 0.82,
              })}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
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
          <Link to="/espace-client" aria-label="Espace client" style={{
            width: 38, height: 38, borderRadius: '50%',
            border: '1px solid var(--border)', background: 'var(--bg-elevated)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15,
          }}>
            👤
          </Link>
          <Link to="/configurateur" className="neo-btn neo-btn-urgent neo-nav-urgent" style={{ padding: '10px 16px', fontSize: 13 }}>
            Urgence / Dépannage
          </Link>
          <Link to="/configurateur" className="neo-btn neo-btn-primary neo-nav-cta">
            Obtenir mon estimation
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
          <Link
            to="/configurateur" onClick={() => setMenuOpen(false)}
            className="neo-btn neo-btn-primary" style={{ marginTop: 12 }}
          >
            Obtenir mon estimation
          </Link>
          <Link
            to="/configurateur" onClick={() => setMenuOpen(false)}
            className="neo-btn neo-btn-urgent" style={{ marginTop: 8 }}
          >
            Urgence / Dépannage
          </Link>
        </div>
      )}

      <style>{`
        @media (max-width: 860px) {
          .neo-nav-desktop { display: none !important; }
          .neo-nav-cta { display: none !important; }
          .neo-nav-toggle { display: flex !important; align-items: center; justify-content: center; }
        }
        @media (max-width: 1280px) {
          .neo-nav-urgent { display: none !important; }
        }
      `}</style>
    </header>
  )
}
