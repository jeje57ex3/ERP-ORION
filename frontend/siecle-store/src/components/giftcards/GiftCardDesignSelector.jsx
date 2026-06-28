import { motion } from 'framer-motion'

const DESIGNS = [
  { id: 'noir',  label: 'Noir Signature', color: '#000', border: '#D8C7A3' },
  { id: 'beige', label: 'Beige Élégance', color: '#D8C7A3', border: '#000' },
  { id: 'dore',  label: 'Doré Nuit', color: 'linear-gradient(135deg, #1a1200, #3d2c00)', border: '#FFD700' },
  { id: 'blanc', label: 'Minimal Blanc', color: '#fff', border: '#111' },
]

export default function GiftCardDesignSelector({ value, onChange }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', color: '#666', marginBottom: 14, textTransform: 'uppercase' }}>Design</div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {DESIGNS.map(d => (
          <motion.button key={d.id} whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.95 }} onClick={() => onChange?.(d.id)}
            style={{ width: 48, height: 48, borderRadius: 12, background: d.color, border: `2px solid ${value === d.id ? d.border : 'transparent'}`, cursor: 'pointer', transition: 'border-color 0.2s', outline: 'none', position: 'relative', transform: value === d.id ? 'scale(1.15)' : 'scale(1)' }}
            title={d.label}>
            {value === d.id && (
              <span style={{ position: 'absolute', bottom: -18, left: '50%', transform: 'translateX(-50%)', fontSize: 9, fontWeight: 700, color: '#fff', whiteSpace: 'nowrap', letterSpacing: '0.05em' }}>✓</span>
            )}
          </motion.button>
        ))}
      </div>
      <div style={{ marginTop: 22, fontSize: 12, color: '#666' }}>{DESIGNS.find(d => d.id === value)?.label}</div>
    </div>
  )
}
