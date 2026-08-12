import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

export default function WorldCard({ number, subtitle, title, image, link, index = 0 }) {
  const [hovered, setHovered] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ delay: index * 0.12, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <Link to={link} style={{ display: 'block' }}>
        <div style={{
          position: 'relative', overflow: 'hidden',
          aspectRatio: '4/5',
          background: image
            ? `center/cover no-repeat url(${image})`
            : 'linear-gradient(160deg, var(--siecle-dark) 0%, var(--siecle-dark-soft) 100%)',
          cursor: 'pointer',
        }}>
          {/* Veil */}
          <div style={{
            position: 'absolute', inset: 0, zIndex: 1,
            background: 'linear-gradient(to top, rgba(9,9,9,0.85) 0%, rgba(9,9,9,0.15) 55%, transparent 100%)',
          }} />

          {/* Border reveal on hover */}
          <motion.div
            animate={{ opacity: hovered ? 1 : 0 }}
            transition={{ duration: 0.3 }}
            style={{ position: 'absolute', inset: 1, border: '1px solid var(--siecle-beige)', zIndex: 2, pointerEvents: 'none' }}
          />

          {/* Content */}
          <div style={{
            position: 'absolute', inset: 0, zIndex: 3,
            display: 'flex', flexDirection: 'column',
            justifyContent: 'flex-end', padding: 32,
          }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
              <span style={{ color: 'var(--siecle-beige)', fontSize: 12, fontWeight: 700, letterSpacing: '0.1em' }}>
                {number}
              </span>
              <span style={{ color: 'var(--siecle-muted)', fontSize: 9, fontWeight: 600, letterSpacing: '0.22em' }}>
                {subtitle}
              </span>
            </div>
            <h3 style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 'clamp(24px, 4vw, 38px)', fontWeight: 700,
              letterSpacing: '0.01em', color: 'var(--siecle-white)',
              textTransform: 'uppercase', marginBottom: 16, lineHeight: 1,
            }}>
              {title}
            </h3>
            <motion.div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <motion.div
                animate={{ width: hovered ? 32 : 18 }}
                transition={{ duration: 0.3 }}
                style={{ height: 1, background: 'var(--siecle-beige)' }}
              />
              <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.16em', color: 'var(--siecle-beige)' }}>
                DÉCOUVRIR
              </span>
            </motion.div>
          </div>
        </div>
      </Link>
    </motion.div>
  )
}
