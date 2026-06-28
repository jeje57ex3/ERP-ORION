import { useState } from 'react'
import { NavLink, Link } from 'react-router-dom'

const NAV = [
  { to: '/lunea/',            label: 'Accueil' },
  { to: '/lunea/soins/',      label: 'Soins' },
  { to: '/lunea/maquillage/', label: 'Maquillage' },
  { to: '/lunea/rituels/',    label: 'Rituels' },
  { to: '/lunea/boutique/',   label: 'Boutique' },
]

export default function LuneaHeader({ cartCount = 0 }) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="lunea-header">
      <div className="lunea-header__inner">
        <Link to="/lunea/" className="lunea-header__logo">LUNEA</Link>

        <nav className="lunea-header__nav" aria-label="Navigation principale">
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => isActive ? 'active' : ''}
              end={to === '/lunea/'}
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="lunea-header__actions">
          <Link to="/lunea/compte/" aria-label="Mon compte" style={{ fontSize: 18, color: 'var(--color-text-muted)' }}>
            &#128100;
          </Link>
          <Link to="/lunea/panier/" aria-label="Panier" className="lunea-cart-badge">
            <span style={{ fontSize: 18, color: 'var(--color-text-muted)' }}>&#128722;</span>
            {cartCount > 0 && (
              <span className="lunea-cart-badge__count">{cartCount}</span>
            )}
          </Link>
        </div>
      </div>
    </header>
  )
}
