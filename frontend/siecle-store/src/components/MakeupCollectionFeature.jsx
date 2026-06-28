import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

const SHADES = [
  { name: 'Or Profond', hex: '#c9a45c' },
  { name: 'Nuit Brune', hex: '#4a3426' },
  { name: 'Terre Cuivrée', hex: '#8b5e3c' },
  { name: 'Bordeaux Sombre', hex: '#6b2737' },
  { name: 'Brun Tabac', hex: '#7a5c3a' },
]

export default function MakeupCollectionFeature() {
  return (
    <section style={{
      background: '#090807',
      padding: '0',
      overflow: 'hidden',
      position: 'relative',
    }}>
      <div style={{
        maxWidth: 1320, margin: '0 auto',
        display: 'grid', gridTemplateColumns: '1fr 1fr',
        minHeight: 620,
      }}
        className="makeup-feature-grid"
      >
        {/* Left — image placeholder */}
        <div style={{ position: 'relative', overflow: 'hidden', minHeight: 400 }}>
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(160deg, #4a3426 0%, #1a0e08 50%, #090807 100%)',
          }} />
          {/* Abstract lipstick/makeup shape */}
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ position: 'relative', width: 200, height: 340 }}>
              {/* Lipstick tube */}
              <div style={{
                position: 'absolute', bottom: 0, left: '50%', transform: 'translateX(-50%)',
                width: 54, height: 200,
                background: 'linear-gradient(180deg, #2a1a10 0%, #1a0e08 100%)',
                borderRadius: '4px 4px 6px 6px',
              }} />
              {/* Lipstick body gold ring */}
              <div style={{
                position: 'absolute', bottom: 195, left: '50%', transform: 'translateX(-50%)',
                width: 58, height: 14,
                background: 'linear-gradient(90deg, #8b6f3a, #c9a45c, #8b6f3a)',
                borderRadius: 2,
              }} />
              {/* Lipstick color */}
              <div style={{
                position: 'absolute', bottom: 209, left: '50%', transform: 'translateX(-50%)',
                width: 50, height: 100,
                background: 'linear-gradient(160deg, #8b2737 0%, #6b1726 100%)',
                borderRadius: '3px 3px 0 0',
                clipPath: 'polygon(0 20%, 100% 0%, 100% 100%, 0% 100%)',
              }} />
              {/* Shine */}
              <div style={{
                position: 'absolute', bottom: 260, left: '50%',
                width: 16, height: 70,
                background: 'rgba(255,255,255,0.08)',
                borderRadius: 8,
                transform: 'translateX(-55%) rotate(-10deg)',
              }} />
            </div>
          </div>
          {/* Gold overlay */}
          <div style={{
            position: 'absolute', inset: 0,
            background: 'radial-gradient(ellipse at 60% 60%, rgba(201,164,92,0.08) 0%, transparent 70%)',
          }} />
        </div>

        {/* Right — text */}
        <div style={{
          display: 'flex', flexDirection: 'column', justifyContent: 'center',
          padding: 'clamp(48px, 6vw, 96px)',
        }}>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.25em', color: '#c9a45c', marginBottom: 20 }}
          >
            NOUVELLE COLLECTION
          </motion.p>

          <motion.h2
            initial={{ opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.12, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            style={{
              fontFamily: '"Playfair Display", "Cormorant Garamond", Georgia, serif',
              fontSize: 'clamp(36px, 5vw, 68px)',
              fontWeight: 500, lineHeight: 1.05,
              color: '#f7f1e8', letterSpacing: '-0.02em',
              marginBottom: 24,
            }}
          >
            Collection<br />Nuit Dorée
          </motion.h2>

          <motion.p
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.28 }}
            style={{ fontSize: 15, lineHeight: 1.8, color: 'rgba(247,241,232,0.55)', maxWidth: 400, marginBottom: 40 }}
          >
            Une palette de teintes profondes et lumineuses, conçue pour les soirées intenses. Rouge bordeaux, or chaud, brun tabac — des nuances qui habillent le regard et les lèvres avec caractère.
          </motion.p>

          {/* Shade swatches */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.38 }}
            style={{ display: 'flex', gap: 10, marginBottom: 40, flexWrap: 'wrap' }}
          >
            {SHADES.map(shade => (
              <div key={shade.name} title={shade.name} style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: '50%',
                  background: shade.hex,
                  border: '2px solid rgba(247,241,232,0.15)',
                  transition: 'transform 0.2s',
                  cursor: 'pointer',
                }}
                  onMouseEnter={e => { e.currentTarget.style.transform = 'scale(1.15)' }}
                  onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)' }}
                />
                <span style={{ fontSize: 9, color: 'rgba(247,241,232,0.35)', whiteSpace: 'nowrap', letterSpacing: '0.05em' }}>
                  {shade.name}
                </span>
              </div>
            ))}
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.48 }}
          >
            <Link to="/boutique?categorie=maquillage&collection=nuit-doree" className="makeup-btn-light">
              Découvrir la collection
            </Link>
          </motion.div>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .makeup-feature-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </section>
  )
}
