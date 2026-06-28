import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { getAccount, getMe } from '../api/customer'
import LuxuryLoader from '../components/LuxuryLoader'

const TIER_COLORS = { classic: '#9E9E9E', silver: '#B8C4CC', gold: '#C0A882', black: '#fff' }

export default function CustomerAccount() {
  const [account, setAccount] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getMe().then(me => {
      if (!me.authenticated) { navigate('/compte/connexion'); return }
      return getAccount()
    }).then(d => {
      if (d) setAccount(d)
    }).catch(() => navigate('/compte/connexion'))
      .finally(() => setLoading(false))
  }, [navigate])

  if (loading) return <LuxuryLoader />
  if (!account) return null

  const { loyalty, affiliate, orders_count = 0 } = account
  const tier = loyalty?.tier || 'classic'
  const tierColor = TIER_COLORS[tier] || '#9E9E9E'

  return (
    <div>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          fontFamily: 'Montserrat, sans-serif',
          fontSize: 28, fontWeight: 900, color: '#fff',
          letterSpacing: '0.04em', marginBottom: 36,
        }}
      >
        TABLEAU DE BORD
      </motion.h1>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 32 }} className="stat-grid">
        {[
          { label: 'POINTS', value: loyalty?.points_balance?.toLocaleString('fr-FR') ?? '0' },
          { label: 'STATUT', value: tier.toUpperCase(), color: tierColor },
          { label: 'COMMANDES', value: orders_count },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            style={{
              background: '#111', border: '1px solid rgba(255,255,255,0.06)',
              padding: '24px 20px', textAlign: 'center',
            }}
          >
            <p style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 36, fontWeight: 900,
              color: stat.color || '#fff', lineHeight: 1, marginBottom: 10,
            }}>
              {stat.value}
            </p>
            <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: '0.18em' }}>
              {stat.label}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Quick links */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {[
          { to: '/compte/commandes', label: 'Mes commandes', sub: `${orders_count} commande${orders_count !== 1 ? 's' : ''}` },
          { to: '/compte/fidelite', label: 'Fidélité & Récompenses', sub: `${loyalty?.points_balance ?? 0} points — Statut ${tier}` },
          { to: '/compte/parrainage', label: 'Programme parrainage', sub: affiliate?.code ? `Code : ${affiliate.code}` : 'Générer mon code' },
          { to: '/compte/carte-cadeau', label: 'Cartes cadeaux', sub: 'Consulter ou activer' },
        ].map((item, i) => (
          <motion.div
            key={item.to}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 + i * 0.07 }}
          >
            <Link to={item.to} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '18px 20px',
              background: '#111', border: '1px solid rgba(255,255,255,0.06)',
              transition: 'border-color 0.2s',
            }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(192,168,130,0.2)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'}
            >
              <div>
                <p style={{ fontSize: 14, fontWeight: 700, color: '#fff', marginBottom: 3 }}>{item.label}</p>
                <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>{item.sub}</p>
              </div>
              <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: 18 }}>→</span>
            </Link>
          </motion.div>
        ))}
      </div>

      <style>{`
        @media (max-width: 600px) { .stat-grid { grid-template-columns: 1fr !important; } }
      `}</style>
    </div>
  )
}
