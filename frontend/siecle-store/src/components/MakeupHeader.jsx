import { useState, useEffect } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useCart } from '../hooks/useCart'

const NAV = [
  { to: '/maquillage', label: 'Accueil' },
  { to: '/boutique?categorie=maquillage', label: 'Boutique' },
  { to: '/boutique?categorie=maquillage&sort=-created_at', label: 'Nouveautés' },
  { to: '/boutique?categorie=maquillage&popular=true', label: 'Best-sellers' },
  { to: '/contact', label: 'Contact' },
]

export default function MakeupHeader() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const { totalItems } = useCart()

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', handler, { passive: true })
    return () => window.removeEventListener('scroll', handler)
  }, [])

  return (
    <>
      <header style={{
        position: 'sticky', top: 0, left: 0, right: 0, zIndex: 200,
        background: scrolled ? 'rgba(247,241,232,0.95)' : 'rgba(247,241,232,0.85)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(74,52,38,0.1)',
        transition: 'background 0.3s, box-shadow 0.3s',
        boxShadow: scrolled ? '0 2px 20px rgba(9,8,7,0.06)' : 'none',
      }}>
        <div style={{
          maxWidth: 1320, margin: '0 auto',
          padding: '0 24px', height: 68,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          {/* Logo */}
          <Link to="/maquillage" style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 18, fontWeight: 900, letterSpacing: '0.12em',
            color: '#090807', textDecoration: 'none',
          }}>
            SIÈCLE
          </Link>

          {/* Desktop nav */}
          <nav style={{ display: 'flex', gap: 36, alignItems: 'center' }} className="makeup-desktop-nav">
            {NAV.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                style={({ isActive }) => ({
                  fontSize: 12, fontWeight: isActive ? 700 : 400,
                  letterSpacing: '0.12em', color: isActive ? '#090807' : '#86796e',
                  textDecoration: 'none', transition: 'color 0.2s',
                })}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* Icons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <Link to="/compte" style={{ color: '#090807', display: 'flex' }} title="Mon compte">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </Link>
            <Link to="/cart" style={{ color: '#090807', display: 'flex', position: 'relative' }} title="Panier">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/>
                <line x1="3" y1="6" x2="21" y2="6"/>
                <path d="M16 10a4 4 0 0 1-8 0"/>
              </svg>
              {totalItems > 0 && (
                <span style={{
                  position: 'absolute', top: -7, right: -7,
                  width: 16, height: 16, borderRadius: '50%',
                  background: '#c9a45c', color: '#fff',
                  fontSize: 9, fontWeight: 800,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {totalItems}
                </span>
              )}
            </Link>

            {/* Burger */}
            <button
              onClick={() => setMenuOpen(o => !o)}
              className="makeup-burger"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#090807', padding: 4 }}
              aria-label="Menu"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                {menuOpen
                  ? <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>
                  : <><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></>
                }
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile menu */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            style={{
              position: 'fixed', top: 68, left: 0, right: 0, zIndex: 190,
              background: '#f7f1e8', borderBottom: '1px solid rgba(74,52,38,0.1)',
              padding: '20px 24px 28px',
            }}
          >
            {NAV.map(item => (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setMenuOpen(false)}
                style={{
                  display: 'block', padding: '14px 0',
                  fontSize: 16, fontWeight: 500, color: '#090807',
                  borderBottom: '1px solid rgba(74,52,38,0.08)',
                  textDecoration: 'none',
                }}
              >
                {item.label}
              </Link>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        .makeup-desktop-nav { display: flex; }
        .makeup-burger { display: none; }
        @media (max-width: 900px) {
          .makeup-desktop-nav { display: none !important; }
          .makeup-burger { display: flex !important; }
        }
      `}</style>
    </>
  )
}
