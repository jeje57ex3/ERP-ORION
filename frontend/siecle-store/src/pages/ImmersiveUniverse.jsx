import { useState } from 'react'
import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import PageTransition from '../components/PageTransition'

const PANELS = [
  {
    id:      'vetements',
    label:   'VÊTEMENTS',
    sub:     'Silhouettes propres,\nmatières douces.',
    to:      '/vetements',
    newTab:  false,
    accent:  '#C8B89A',
    bg:      'linear-gradient(160deg, #0d0d0d 0%, #1a1810 100%)',
    letter:  'V',
  },
  {
    id:      'montres',
    label:   'MONTRES',
    sub:     'Design minimaliste,\nsignal d\'identité.',
    to:      '/montres',
    newTab:  false,
    accent:  '#C0A882',
    bg:      'linear-gradient(160deg, #0e0b08 0%, #2a1f14 100%)',
    letter:  'M',
  },
  {
    id:      'maquillage',
    label:   'MAQUILLAGE',
    sub:     'Formules douces,\ntoutes les carnations.',
    to:      '/maquillage',
    newTab:  true,
    accent:  '#c9957a',
    bg:      'linear-gradient(160deg, #0e080c 0%, #231420 100%)',
    letter:  'B',
  },
]

function Panel({ p, hovered, onHover }) {
  const isActive = hovered === p.id || hovered === null

  const inner = (
    <motion.div
      style={{
        flex: hovered === p.id ? 2.2 : 1,
        minWidth: 0,
        background: p.bg,
        position: 'relative',
        overflow: 'hidden',
        cursor: 'pointer',
        transition: 'flex 0.55s cubic-bezier(0.22,1,0.36,1)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onMouseEnter={() => onHover(p.id)}
      onMouseLeave={() => onHover(null)}
    >
      {/* Watermark letter */}
      <motion.p
        animate={{ opacity: hovered === p.id ? 0.07 : 0.03, scale: hovered === p.id ? 1.08 : 1 }}
        transition={{ duration: 0.5 }}
        style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'Montserrat, sans-serif',
          fontSize: 'clamp(180px, 25vw, 360px)',
          fontWeight: 900, color: p.accent,
          margin: 0, pointerEvents: 'none', userSelect: 'none',
        }}
      >
        {p.letter}
      </motion.p>

      {/* Border on hover */}
      <motion.div
        animate={{ opacity: hovered === p.id ? 1 : 0 }}
        transition={{ duration: 0.3 }}
        style={{ position: 'absolute', inset: 1, border: `1px solid ${p.accent}22`, pointerEvents: 'none' }}
      />

      {/* Content */}
      <div style={{ position: 'relative', zIndex: 2, padding: '0 40px', textAlign: 'center' }}>
        <motion.p
          animate={{ opacity: hovered === p.id ? 1 : 0.5, y: hovered === p.id ? 0 : 4 }}
          transition={{ duration: 0.4 }}
          style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', color: p.accent, marginBottom: 16 }}
        >
          {p.label}
        </motion.p>

        <motion.h2
          animate={{ opacity: hovered === p.id ? 1 : 0.7 }}
          transition={{ duration: 0.4 }}
          style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 'clamp(26px, 3vw, 42px)',
            fontWeight: 900, color: '#fff',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            margin: '0 0 20px',
          }}
        >
          {p.label}
        </motion.h2>

        <motion.p
          animate={{ opacity: hovered === p.id ? 0.55 : 0 }}
          transition={{ duration: 0.35, delay: 0.05 }}
          style={{ color: '#fff', fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-line', marginBottom: 32 }}
        >
          {p.sub}
        </motion.p>

        <motion.div
          animate={{ opacity: hovered === p.id ? 1 : 0, y: hovered === p.id ? 0 : 8 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}
        >
          <div style={{ width: 24, height: 1, background: p.accent }} />
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.16em', color: p.accent }}>
            DÉCOUVRIR {p.newTab ? '↗' : ''}
          </span>
          <div style={{ width: 24, height: 1, background: p.accent }} />
        </motion.div>
      </div>
    </motion.div>
  )

  return p.newTab
    ? <a href={p.to} target="_blank" rel="noopener noreferrer" style={{ flex: 1, display: 'flex', textDecoration: 'none', minWidth: 0 }}>{inner}</a>
    : <Link to={p.to} style={{ flex: 1, display: 'flex', textDecoration: 'none', minWidth: 0 }}>{inner}</Link>
}

export default function ImmersiveUniverse() {
  const [hovered, setHovered] = useState(null)

  return (
    <PageTransition>
      <div style={{ background: '#000', minHeight: '100vh' }}>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8 }}
          style={{ position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10, padding: '32px 40px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        >
          <p style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 10, fontWeight: 800, letterSpacing: '0.24em', color: 'rgba(255,255,255,0.35)' }}>
            NOS UNIVERS
          </p>
          <Link to="/" style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', color: 'rgba(255,255,255,0.3)', textDecoration: 'none' }}>
            ← ACCUEIL
          </Link>
        </motion.div>

        {/* Panels */}
        <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }} className="immersive-panels">
          {PANELS.map(p => (
            <Panel key={p.id} p={p} hovered={hovered} onHover={setHovered} />
          ))}
        </div>

        {/* Bottom hint */}
        <motion.p
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8, duration: 0.6 }}
          style={{ position: 'absolute', bottom: 28, left: 0, right: 0, textAlign: 'center', fontSize: 9, letterSpacing: '0.22em', color: 'rgba(255,255,255,0.2)' }}
        >
          SURVOLEZ UN UNIVERS POUR L'EXPLORER
        </motion.p>

        <style>{`
          @media (max-width: 768px) {
            .immersive-panels { flex-direction: column !important; height: auto !important; }
            .immersive-panels > * { min-height: 33vh !important; }
          }
        `}</style>
      </div>
    </PageTransition>
  )
}
