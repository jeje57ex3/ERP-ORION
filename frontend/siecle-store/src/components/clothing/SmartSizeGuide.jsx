import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const SIZE_TABLE = {
  XS:  { chest: [80, 84], waist: [62, 66] },
  S:   { chest: [84, 88], waist: [66, 70] },
  M:   { chest: [88, 92], waist: [70, 74] },
  L:   { chest: [92, 96], waist: [74, 78] },
  XL:  { chest: [96, 100], waist: [78, 82] },
  XXL: { chest: [100, 104], waist: [82, 86] },
  '3XL': { chest: [104, 108], waist: [86, 90] },
  '4XL': { chest: [108, 116], waist: [90, 98] },
}

function recommend(chest, fit = 'normal') {
  const sizes = Object.keys(SIZE_TABLE)
  for (const size of sizes) {
    const [lo, hi] = SIZE_TABLE[size].chest
    if (chest >= lo && chest <= hi) {
      if (fit === 'oversize') return sizes[Math.min(sizes.indexOf(size) + 1, sizes.length - 1)]
      return size
    }
  }
  return 'M'
}

export default function SmartSizeGuide({ productId }) {
  const [chest, setChest] = useState('')
  const [fit, setFit] = useState('normal')
  const [result, setResult] = useState(null)

  const calc = () => { if (chest) setResult(recommend(Number(chest), fit)) }

  return (
    <div style={{ background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 24 }}>
      <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.16em', color: 'var(--siecle-beige)', marginBottom: 18 }}>GUIDE TAILLE RAPIDE</div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        <input type="number" value={chest} onChange={e => setChest(e.target.value)} placeholder="Tour poitrine (cm)"
          style={{ flex: 1, background: '#111', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '10px 14px', color: '#fff', fontSize: 13, outline: 'none' }} />
        <select value={fit} onChange={e => setFit(e.target.value)}
          style={{ background: '#111', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '10px 14px', color: '#aaa', fontSize: 12, outline: 'none', cursor: 'pointer' }}>
          <option value="ajuste">Ajusté</option>
          <option value="normal">Normal</option>
          <option value="oversize">Oversize</option>
        </select>
      </div>
      <button onClick={calc}
        style={{ width: '100%', padding: '11px', background: '#fff', color: '#000', border: 'none', borderRadius: 8, fontSize: 11, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer', marginBottom: 12 }}>
        TROUVER MA TAILLE
      </button>
      <AnimatePresence>
        {result && (
          <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
            style={{ textAlign: 'center', padding: 16, background: 'rgba(216,199,163,0.06)', border: '1px solid rgba(216,199,163,0.15)', borderRadius: 10 }}>
            <div style={{ fontSize: 11, color: 'var(--siecle-beige)', letterSpacing: '0.2em', marginBottom: 4 }}>VOTRE TAILLE</div>
            <div style={{ fontSize: 40, fontWeight: 900, color: '#fff' }}>{result}</div>
            <a href="/guide-taille" style={{ fontSize: 11, color: '#555', marginTop: 6, display: 'block', textDecoration: 'none' }}>Guide complet →</a>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
