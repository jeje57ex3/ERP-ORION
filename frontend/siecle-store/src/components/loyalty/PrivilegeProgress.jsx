import { motion } from 'framer-motion'

const PRIVILEGES = [
  { id: 'livraison', label: 'Livraison offerte dès 50€', tier: 'BRONZE', icon: '🚚' },
  { id: 'retours', label: 'Retours gratuits 30 jours', tier: 'BRONZE', icon: '↩️' },
  { id: 'early-access', label: 'Accès anticipé aux drops', tier: 'SILVER', icon: '⚡' },
  { id: 'birthday', label: 'Cadeau anniversaire', tier: 'SILVER', icon: '🎁' },
  { id: 'configurator', label: 'Configurateur montre prioritaire', tier: 'GOLD', icon: '⌚' },
  { id: 'concierge', label: 'Service conciergerie dédié', tier: 'GOLD', icon: '💬' },
  { id: 'invite', label: 'Invitations événements exclusifs', tier: 'PLATINUM', icon: '🎫' },
  { id: 'custom', label: 'Commandes sur-mesure', tier: 'PLATINUM', icon: '✨' },
]

const TIER_ORDER = ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM']

export default function PrivilegeProgress({ currentTier = 'BRONZE' }) {
  const tierIdx = TIER_ORDER.indexOf(currentTier)
  const unlocked = (tier) => TIER_ORDER.indexOf(tier) <= tierIdx

  return (
    <div>
      {TIER_ORDER.map(tier => (
        <div key={tier} style={{ marginBottom: 32 }}>
          <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.2em', color: unlocked(tier) ? 'var(--siecle-beige)' : '#333', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
            {tier} {unlocked(tier) && <span style={{ color: '#48C78E' }}>✓</span>}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            {PRIVILEGES.filter(p => p.tier === tier).map(p => (
              <motion.div key={p.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', background: unlocked(tier) ? 'rgba(216,199,163,0.05)' : '#0a0a0a', border: `1px solid ${unlocked(tier) ? 'rgba(216,199,163,0.15)' : 'rgba(255,255,255,0.04)'}`, borderRadius: 12, opacity: unlocked(tier) ? 1 : 0.4 }}>
                <span style={{ fontSize: 18 }}>{p.icon}</span>
                <span style={{ fontSize: 12, color: unlocked(tier) ? '#ddd' : '#444', fontWeight: 600 }}>{p.label}</span>
              </motion.div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
