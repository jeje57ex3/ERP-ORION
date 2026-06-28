import { motion } from 'framer-motion'
import '../../styles/loyalty.css'

const TIERS = [
  { name: 'BRONZE',   min: 0,     max: 999,   color: '#CD7F32' },
  { name: 'SILVER',   min: 1000,  max: 4999,  color: '#C0C0C0' },
  { name: 'GOLD',     min: 5000,  max: 14999, color: '#D8C7A3' },
  { name: 'PLATINUM', min: 15000, max: Infinity, color: '#fff' },
]

const getTier = (pts) => TIERS.find(t => pts >= t.min && pts <= t.max) || TIERS[0]
const getProgress = (pts) => {
  const t = getTier(pts)
  if (t.max === Infinity) return 100
  return Math.round(((pts - t.min) / (t.max - t.min)) * 100)
}

export default function LoyaltySummary({ points = 0, compact = false }) {
  const tier = getTier(points)
  const progress = getProgress(points)
  const nextTier = TIERS[TIERS.indexOf(tier) + 1]

  if (compact) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ color: tier.color, fontWeight: 800, fontSize: 14 }}>{points.toLocaleString('fr-FR')}</span>
        <span style={{ fontSize: 11, color: '#666', letterSpacing: '0.12em' }}>PTS · {tier.name}</span>
      </div>
    )
  }

  return (
    <div style={{ background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 20, padding: 28 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <div className="points-display" style={{ fontSize: 48 }}>{points.toLocaleString('fr-FR')}</div>
          <div className="points-label">POINTS SIÈCLE</div>
        </div>
        <span className={`tier-badge ${tier.name.toLowerCase()}`}>{tier.name}</span>
      </div>
      <div className="tier-bar">
        <div className="tier-track">
          <motion.div className="tier-fill" initial={{ width: 0 }} animate={{ width: `${progress}%` }} transition={{ duration: 1.2, ease: 'easeOut' }} />
        </div>
        <div className="tier-labels">
          <span>{tier.min.toLocaleString('fr-FR')} pts</span>
          {nextTier && <span>{nextTier.min.toLocaleString('fr-FR')} pts → {nextTier.name}</span>}
        </div>
      </div>
      {nextTier && (
        <p style={{ fontSize: 12, color: '#555', marginTop: 12 }}>
          Il vous reste <strong style={{ color: '#fff' }}>{(nextTier.min - points).toLocaleString('fr-FR')} points</strong> pour atteindre le niveau {nextTier.name}.
        </p>
      )}
    </div>
  )
}
