import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { logout, getMe } from '../api/customer'

const NAV = [
  { to: '/compte',           label: 'Tableau de bord', end: true },
  { to: '/compte/commandes', label: 'Commandes' },
  { to: '/compte/fidelite',  label: 'Fidélité & Récompenses' },
  { to: '/compte/parrainage', label: 'Parrainage' },
  { to: '/compte/carte-cadeau', label: 'Cartes cadeaux' },
]

export default function CustomerAccountLayout() {
  const [user, setUser] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    getMe().then(me => {
      if (me.authenticated) setUser(me.user)
      else navigate('/compte/connexion')
    }).catch(() => navigate('/compte/connexion'))
  }, [navigate])

  const handleLogout = async () => {
    try { await logout() } catch {}
    localStorage.removeItem('siecle_token')
    navigate('/')
  }

  return (
    <div style={{ minHeight: '100vh', background: '#000', padding: '80px 24px 60px' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto', display: 'grid', gridTemplateColumns: '220px 1fr', gap: 48 }} className="account-grid">
        {/* Sidebar */}
        <div>
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            style={{ position: 'sticky', top: 100 }}
          >
            <div style={{ marginBottom: 32 }}>
              <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', letterSpacing: '0.18em', marginBottom: 6 }}>
                BIENVENUE
              </p>
              <p style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>
                {user?.first_name || user?.username || user?.email?.split('@')[0]}
              </p>
            </div>

            <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {NAV.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  style={({ isActive }) => ({
                    display: 'block', padding: '10px 14px',
                    fontSize: 13, fontWeight: isActive ? 700 : 400,
                    color: isActive ? '#C0A882' : 'rgba(255,255,255,0.45)',
                    borderLeft: `2px solid ${isActive ? '#C0A882' : 'transparent'}`,
                    transition: 'all 0.2s',
                  })}
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>

            <button
              onClick={handleLogout}
              style={{
                marginTop: 32,
                background: 'transparent', border: 'none',
                color: 'rgba(255,255,255,0.25)', fontSize: 12,
                letterSpacing: '0.12em', cursor: 'pointer',
                padding: '10px 14px', textAlign: 'left',
                transition: 'color 0.2s',
              }}
              onMouseEnter={e => { e.currentTarget.style.color = '#fff' }}
              onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.25)' }}
            >
              SE DÉCONNECTER
            </button>
          </motion.div>
        </div>

        {/* Content */}
        <motion.main
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Outlet />
        </motion.main>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .account-grid { grid-template-columns: 1fr !important; gap: 24px !important; }
        }
      `}</style>
    </div>
  )
}
