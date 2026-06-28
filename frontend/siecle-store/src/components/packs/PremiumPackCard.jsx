import { useState } from 'react'
import { motion } from 'framer-motion'

export default function PremiumPackCard({ pack, onAdd }) {
  const [added, setAdded] = useState(false)
  const saving = Math.round(((pack.normalPrice - pack.price) / pack.normalPrice) * 100)

  const handleAdd = async () => {
    setAdded(true)
    onAdd?.(pack)
    setTimeout(() => setAdded(false), 2200)
  }

  return (
    <motion.div whileHover={{ y: -6 }} transition={{ type: 'spring', stiffness: 300 }}
      style={{ background: 'linear-gradient(145deg, #0d0d0d, #111)', border: `1px solid ${added ? 'rgba(72,199,142,0.4)' : 'rgba(255,255,255,0.07)'}`, borderRadius: 22, overflow: 'hidden', transition: 'border-color 0.4s', position: 'relative' }}>
      {pack.badge && (
        <span style={{ position: 'absolute', top: 16, right: 16, fontSize: 10, fontWeight: 800, letterSpacing: '0.14em', padding: '5px 12px', background: 'rgba(216,199,163,0.12)', border: '1px solid rgba(216,199,163,0.2)', borderRadius: 999, color: 'var(--siecle-beige)' }}>
          {pack.badge}
        </span>
      )}
      <div style={{ height: 6, background: `linear-gradient(90deg, ${pack.color || '#111'}, #1a1a1a)` }} />
      <div style={{ padding: '28px 28px 24px' }}>
        <div style={{ fontSize: 18, fontWeight: 900, color: '#fff', letterSpacing: '0.06em', marginBottom: 20 }}>{pack.name}</div>
        <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 24px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {pack.items?.map(item => (
            <li key={item} style={{ fontSize: 13, color: '#888', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: 'var(--siecle-beige)', fontSize: 10 }}>✦</span> {item}
            </li>
          ))}
        </ul>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 8 }}>
          <span style={{ fontSize: 28, fontWeight: 900, color: '#fff' }}>{pack.price} €</span>
          <span style={{ fontSize: 14, color: '#444', textDecoration: 'line-through' }}>{pack.normalPrice} €</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: '#48C78E' }}>-{saving}%</span>
        </div>
        {pack.points && (
          <div style={{ fontSize: 12, color: '#555', marginBottom: 20 }}>+{pack.points.toLocaleString('fr-FR')} points de fidélité</div>
        )}
        <motion.button onClick={handleAdd} whileTap={{ scale: 0.97 }}
          style={{ width: '100%', padding: '14px', background: added ? '#48C78E' : '#fff', color: added ? '#fff' : '#000', border: 'none', borderRadius: 10, fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer', transition: 'background 0.3s' }}>
          {added ? 'AJOUTÉ AU PANIER ✓' : 'CHOISIR CE PACK'}
        </motion.button>
      </div>
    </motion.div>
  )
}
