import { motion } from 'framer-motion'

const ICONS = { vetements: '👕', montres: '⌚', maquillage: '💄' }

export default function CompleteLookCard({ look, onAdd }) {
  const total = look.items?.reduce((s, i) => s + (i.price || 0), 0) || 0

  return (
    <motion.div whileHover={{ y: -4, borderColor: 'rgba(216,199,163,0.25)' }}
      style={{ background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 20, overflow: 'hidden', transition: 'border-color 0.3s' }}>
      {/* Visual */}
      <div style={{ height: 220, background: '#111', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, padding: 24, position: 'relative' }}>
        {look.items?.slice(0, 3).map((item, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
            style={{ width: 64, height: 64, background: '#1a1a1a', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28 }}>
            {ICONS[item.category] || '📦'}
          </motion.div>
        ))}
        {look.curated && (
          <span style={{ position: 'absolute', top: 16, left: 16, fontSize: 10, fontWeight: 700, letterSpacing: '0.15em', padding: '4px 10px', background: 'rgba(216,199,163,0.15)', border: '1px solid rgba(216,199,163,0.25)', borderRadius: 999, color: 'var(--siecle-beige)' }}>CURATED</span>
        )}
      </div>
      {/* Info */}
      <div style={{ padding: 20 }}>
        <div style={{ fontSize: 15, fontWeight: 800, color: '#fff', marginBottom: 4 }}>{look.name}</div>
        <div style={{ fontSize: 12, color: '#555', marginBottom: 14, lineHeight: 1.5 }}>
          {look.items?.map(i => i.name).join(' · ')}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <span style={{ fontSize: 18, fontWeight: 800, color: 'var(--siecle-beige)' }}>{total} €</span>
            {look.savings > 0 && <span style={{ fontSize: 11, color: '#48C78E', marginLeft: 8 }}>-{look.savings} € économisés</span>}
          </div>
          <button onClick={() => onAdd?.(look)}
            style={{ padding: '10px 20px', background: '#fff', color: '#000', border: 'none', borderRadius: 8, fontSize: 11, fontWeight: 800, letterSpacing: '0.12em', cursor: 'pointer' }}>
            ADOPTER CE LOOK
          </button>
        </div>
      </div>
    </motion.div>
  )
}
