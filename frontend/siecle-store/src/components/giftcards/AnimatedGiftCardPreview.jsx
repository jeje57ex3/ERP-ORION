import { useState } from 'react'
import { motion } from 'framer-motion'

export default function AnimatedGiftCardPreview({ design, amount, recipient, message }) {
  const [flipped, setFlipped] = useState(false)

  const DESIGNS = {
    noir:    { bg: '#000', text: '#D8C7A3', accent: '#D8C7A3', label: 'Noir Signature' },
    beige:   { bg: '#D8C7A3', text: '#000', accent: '#000', label: 'Beige Élégance' },
    dore:    { bg: 'linear-gradient(135deg, #1a1200, #3d2c00)', text: '#FFD700', accent: '#FFD700', label: 'Doré Nuit' },
    blanc:   { bg: '#fff', text: '#111', accent: '#111', label: 'Minimal Blanc' },
  }

  const d = DESIGNS[design] || DESIGNS.noir

  return (
    <div style={{ perspective: 1200, width: 320, height: 200, cursor: 'pointer' }} onClick={() => setFlipped(f => !f)}>
      <motion.div animate={{ rotateY: flipped ? 180 : 0 }} transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
        style={{ position: 'relative', width: '100%', height: '100%', transformStyle: 'preserve-3d' }}>
        {/* Front */}
        <div style={{ position: 'absolute', inset: 0, borderRadius: 18, background: d.bg, padding: '24px 28px', backfaceVisibility: 'hidden', boxShadow: '0 24px 60px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div style={{ fontSize: 18, fontWeight: 900, letterSpacing: '0.2em', color: d.text }}>SIÈCLE</div>
          <div>
            <div style={{ fontSize: 36, fontWeight: 900, color: d.text, lineHeight: 1 }}>{amount} €</div>
            <div style={{ fontSize: 11, color: d.text, opacity: 0.6, letterSpacing: '0.12em', marginTop: 4 }}>CARTE CADEAU</div>
          </div>
          <div style={{ fontSize: 10, color: d.text, opacity: 0.4 }}>Retournez pour voir le message →</div>
        </div>
        {/* Back */}
        <div style={{ position: 'absolute', inset: 0, borderRadius: 18, background: d.bg, padding: '24px 28px', backfaceVisibility: 'hidden', transform: 'rotateY(180deg)', boxShadow: '0 24px 60px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            {recipient && <div style={{ fontSize: 12, color: d.text, opacity: 0.7, marginBottom: 6 }}>Pour {recipient},</div>}
            <div style={{ fontSize: 13, color: d.text, lineHeight: 1.6, opacity: 0.85 }}>{message || 'Un cadeau SIÈCLE pour toi ✨'}</div>
          </div>
          <div style={{ fontFamily: 'monospace', fontSize: 12, color: d.text, opacity: 0.5, letterSpacing: '0.18em' }}>SIECLE-XXXX-XXXX</div>
        </div>
      </motion.div>
    </div>
  )
}
