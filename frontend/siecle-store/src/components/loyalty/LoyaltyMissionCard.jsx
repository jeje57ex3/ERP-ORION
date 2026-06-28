import { motion } from 'framer-motion'
import '../../styles/loyalty.css'

export default function LoyaltyMissionCard({ mission, onComplete }) {
  const { title, description, icon, points, done, progress, total } = mission
  return (
    <motion.div className={`mission-card ${done ? 'done' : ''}`} whileHover={done ? {} : { x: 4 }}>
      <div className="mission-icon">{icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: done ? '#555' : '#fff', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
          {title}
          {done && <span style={{ fontSize: 10, color: '#48C78E', letterSpacing: '0.1em' }}>COMPLÉTÉ ✓</span>}
        </div>
        <div style={{ fontSize: 12, color: '#555', marginBottom: progress !== undefined ? 10 : 0 }}>{description}</div>
        {progress !== undefined && !done && (
          <div>
            <div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 999, overflow: 'hidden' }}>
              <div style={{ width: `${(progress / total) * 100}%`, height: '100%', background: 'var(--siecle-beige)', borderRadius: 999, transition: 'width 0.6s ease' }} />
            </div>
            <div style={{ fontSize: 11, color: '#555', marginTop: 4 }}>{progress}/{total}</div>
          </div>
        )}
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--siecle-beige)' }}>+{points}</div>
        <div style={{ fontSize: 10, color: '#555', letterSpacing: '0.1em' }}>PTS</div>
        {!done && (
          <button onClick={() => onComplete?.(mission)} style={{ marginTop: 8, padding: '6px 14px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#aaa', borderRadius: 6, fontSize: 11, cursor: 'pointer', fontWeight: 600 }}>
            Valider
          </button>
        )}
      </div>
    </motion.div>
  )
}
