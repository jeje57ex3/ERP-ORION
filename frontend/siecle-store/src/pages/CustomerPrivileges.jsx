import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { getMe, getRewards } from '../api/customer'
import { fadeUp, staggerContainer } from '../utils/animations'
import PageTransition from '../components/PageTransition'

const TIERS = [
  { key: 'classic', label: 'Classic', min: 0,    color: '#888' },
  { key: 'silver',  label: 'Silver',  min: 500,  color: '#B0B8C4' },
  { key: 'gold',    label: 'Gold',    min: 1500, color: '#C9A45C' },
  { key: 'black',   label: 'Black',   min: 3000, color: '#fff' },
]

const BADGES_DEMO = [
  { type: 'client_signature', label: 'Client Signature', icon: '✦', color: '#C8B89A' },
  { type: 'early_access',     label: 'Early Access',     icon: '◆', color: '#9090B0' },
]

const PERKS = [
  { tier: 'classic', items: ['Livraison standard', 'Programme points', 'Newsletters exclusives'] },
  { tier: 'silver',  items: ['Livraison prioritaire', '+20% points',    'Accès early sales'] },
  { tier: 'gold',    items: ['Livraison offerte',    '+50% points',    'Drops privés', 'Service dédié'] },
  { tier: 'black',   items: ['Service personnalisé', '×2 points',      'Éditions exclusives', 'Certificats', 'Early drops'] },
]

export default function CustomerPrivileges() {
  const [loyalty, setLoyalty] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    getMe().then(me => {
      if (!me.authenticated) { navigate('/compte/connexion'); return }
      return getRewards()
    }).then(d => { if (d) setLoyalty(d) }).catch(() => {})
  }, [navigate])

  const pts    = loyalty?.points || 0
  const tier   = loyalty?.tier   || 'classic'
  const tierData = TIERS.find(t => t.key === tier) || TIERS[0]
  const nextTier = TIERS[TIERS.findIndex(t => t.key === tier) + 1]
  const toNext   = nextTier ? Math.max(0, nextTier.min - pts) : 0
  const progress = nextTier ? Math.min(100, ((pts - tierData.min) / (nextTier.min - tierData.min)) * 100) : 100

  return (
    <PageTransition>
      <div>
        {/* Header */}
        <motion.div variants={fadeUp} initial="hidden" animate="visible" style={{ marginBottom: 40 }}>
          <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.24em', color: 'var(--siecle-beige)', marginBottom: 10 }}>ESPACE CLIENT</p>
          <h1 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 28, fontWeight: 900, color: '#fff' }}>MES PRIVILÈGES</h1>
        </motion.div>

        {/* Niveau actuel */}
        <motion.div variants={fadeUp} initial="hidden" animate="visible" transition={{ delay: 0.1 }}
          style={{ background: '#111', border: '1px solid rgba(255,255,255,0.06)', padding: 32, marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
            <div>
              <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.2em', color: tierData.color, marginBottom: 6 }}>NIVEAU ACTUEL</p>
              <p style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 32, fontWeight: 900, color: tierData.color }}>{tierData.label.toUpperCase()}</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.2em', color: 'rgba(255,255,255,0.3)', marginBottom: 6 }}>POINTS</p>
              <p style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 32, fontWeight: 900, color: '#fff' }}>{pts.toLocaleString('fr-FR')}</p>
            </div>
          </div>

          {nextTier && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>Prochain niveau : {nextTier.label}</p>
                <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>{toNext} points restants</p>
              </div>
              <div style={{ height: 2, background: 'rgba(255,255,255,0.08)', borderRadius: 1 }}>
                <motion.div
                  initial={{ width: 0 }} animate={{ width: `${progress}%` }}
                  transition={{ duration: 1, delay: 0.4 }}
                  style={{ height: '100%', background: tierData.color, borderRadius: 1 }}
                />
              </div>
            </>
          )}
        </motion.div>

        {/* Badges */}
        <motion.div variants={staggerContainer} initial="hidden" animate="visible" style={{ marginBottom: 24 }}>
          <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.2em', color: 'var(--siecle-beige)', marginBottom: 16 }}>MES BADGES</p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {BADGES_DEMO.map(b => (
              <motion.div key={b.type} variants={fadeUp}
                style={{ padding: '12px 20px', background: '#111', border: `1px solid ${b.color}33`, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ color: b.color }}>{b.icon}</span>
                <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: b.color }}>{b.label}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Avantages par niveau */}
        <motion.div variants={fadeUp} initial="hidden" animate="visible" transition={{ delay: 0.3 }}>
          <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.2em', color: 'var(--siecle-beige)', marginBottom: 16 }}>AVANTAGES PAR NIVEAU</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }} className="perks-grid">
            {PERKS.map(p => {
              const t = TIERS.find(x => x.key === p.tier)
              const isActive = TIERS.findIndex(x => x.key === p.tier) <= TIERS.findIndex(x => x.key === tier)
              return (
                <div key={p.tier} style={{ padding: 20, background: '#111', border: `1px solid ${isActive ? t.color + '33' : 'rgba(255,255,255,0.06)'}`, opacity: isActive ? 1 : 0.5 }}>
                  <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.16em', color: t.color, marginBottom: 14 }}>{t.label.toUpperCase()}</p>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {p.items.map(item => (
                      <li key={item} style={{ fontSize: 12, color: 'rgba(255,255,255,0.45)', paddingLeft: 14, position: 'relative' }}>
                        <span style={{ position: 'absolute', left: 0, color: t.color }}>—</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
        </motion.div>

        <style>{`@media (max-width: 768px) { .perks-grid { grid-template-columns: repeat(2,1fr) !important; } }`}</style>
      </div>
    </PageTransition>
  )
}
