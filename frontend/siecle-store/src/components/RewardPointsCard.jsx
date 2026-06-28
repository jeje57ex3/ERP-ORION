import { motion } from 'framer-motion'

const TIERS = [
  { key: 'classic', label: 'Classic', min: 0,    max: 499,  color: '#9E9E9E' },
  { key: 'silver',  label: 'Silver',  min: 500,  max: 999,  color: '#B8C4CC' },
  { key: 'gold',    label: 'Gold',    min: 1000, max: 2999, color: '#C0A882' },
  { key: 'black',   label: 'Black',   min: 3000, max: null, color: '#fff' },
]

const REWARDS = [
  { id: 'r100',  points: 100,  label: '5 € de réduction',  type: 'discount' },
  { id: 'r250',  points: 250,  label: '15 € de réduction', type: 'discount' },
  { id: 'r500',  points: 500,  label: '40 € de réduction', type: 'discount' },
  { id: 'r1000', points: 1000, label: 'Accès drop privé',  type: 'premium' },
]

export default function RewardPointsCard({ loyalty, onUseReward }) {
  if (!loyalty) return null

  const { points_balance = 0, lifetime_points = 0, tier = 'classic', history = [] } = loyalty
  const tierInfo = TIERS.find(t => t.key === tier) || TIERS[0]
  const nextTier = TIERS[TIERS.indexOf(tierInfo) + 1]
  const progressMax = nextTier ? nextTier.min : points_balance
  const progress = nextTier ? Math.min(points_balance / nextTier.min, 1) : 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Points balance */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          background: '#111', border: '1px solid rgba(255,255,255,0.06)',
          padding: 32,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, letterSpacing: '0.15em', marginBottom: 8 }}>
              SOLDE DE POINTS
            </p>
            <p style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 48, fontWeight: 900, color: '#fff', lineHeight: 1,
            }}>
              {points_balance.toLocaleString('fr-FR')}
            </p>
          </div>
          <div style={{
            padding: '6px 14px',
            border: `1px solid ${tierInfo.color}44`,
            color: tierInfo.color,
            fontSize: 10, fontWeight: 800, letterSpacing: '0.18em',
          }}>
            {tierInfo.label.toUpperCase()}
          </div>
        </div>

        {/* Progress to next tier */}
        {nextTier && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', letterSpacing: '0.1em' }}>
                Prochain palier : {nextTier.label}
              </span>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
                {points_balance} / {nextTier.min}
              </span>
            </div>
            <div style={{ height: 2, background: 'rgba(255,255,255,0.06)', borderRadius: 1 }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progress * 100}%` }}
                transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
                style={{ height: '100%', background: tierInfo.color, borderRadius: 1 }}
              />
            </div>
            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', marginTop: 8 }}>
              Encore {nextTier.min - points_balance} pts pour accéder au statut {nextTier.label}
            </p>
          </div>
        )}
      </motion.div>

      {/* Available rewards */}
      <div>
        <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, letterSpacing: '0.15em', marginBottom: 14 }}>
          RÉCOMPENSES DISPONIBLES
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {REWARDS.map((reward, i) => {
            const canUse = points_balance >= reward.points
            return (
              <motion.div
                key={reward.id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.08 }}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '16px 20px',
                  background: canUse ? 'rgba(192,168,130,0.04)' : 'transparent',
                  border: `1px solid ${canUse ? 'rgba(192,168,130,0.15)' : 'rgba(255,255,255,0.05)'}`,
                  opacity: canUse ? 1 : 0.45,
                }}
              >
                <div>
                  <p style={{ color: '#fff', fontSize: 14, fontWeight: 700, marginBottom: 3 }}>{reward.label}</p>
                  <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12 }}>{reward.points} pts requis</p>
                </div>
                {canUse && onUseReward && (
                  <button
                    onClick={() => onUseReward(reward.id)}
                    style={{
                      padding: '8px 18px',
                      background: 'transparent',
                      border: '1px solid rgba(192,168,130,0.4)',
                      color: '#C0A882', fontSize: 11, fontWeight: 700, letterSpacing: '0.12em',
                      cursor: 'pointer', transition: 'all 0.2s',
                    }}
                    onMouseEnter={e => { e.currentTarget.style.background = '#C0A882'; e.currentTarget.style.color = '#000' }}
                    onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#C0A882' }}
                  >
                    UTILISER
                  </button>
                )}
              </motion.div>
            )
          })}
        </div>
      </div>

      {/* Transaction history */}
      {history.length > 0 && (
        <div>
          <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, letterSpacing: '0.15em', marginBottom: 14 }}>
            HISTORIQUE
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {history.slice(0, 8).map((tx, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '12px 0',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
              }}>
                <div>
                  <p style={{ fontSize: 13, color: '#fff' }}>{tx.reason || tx.transaction_type}</p>
                  <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
                    {tx.created_at ? new Date(tx.created_at).toLocaleDateString('fr-FR') : ''}
                  </p>
                </div>
                <p style={{
                  fontSize: 14, fontWeight: 700,
                  color: tx.points > 0 ? '#C0A882' : 'rgba(255,255,255,0.4)',
                }}>
                  {tx.points > 0 ? '+' : ''}{tx.points} pts
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
