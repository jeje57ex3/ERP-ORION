import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

const UNIVERSE_STYLES = {
  vetements: {
    accent: '#C8B89A',
    bg: 'linear-gradient(160deg, #111 0%, #1C1C1C 100%)',
    label: 'VÊTEMENTS',
  },
  montres: {
    accent: '#C0A882',
    bg: 'linear-gradient(160deg, #0E0B08 0%, #2A1F14 100%)',
    label: 'MONTRES',
  },
  maquillage: {
    accent: '#C99AAA',
    bg: 'linear-gradient(160deg, #0E080C 0%, #231420 100%)',
    label: 'MAQUILLAGE',
  },
}

export default function UniverseCard({ slug, title, description, link, index = 0, tall = false, newTab = false }) {
  const [hovered, setHovered] = useState(false)
  const style = UNIVERSE_STYLES[slug] || { accent: 'var(--siecle-beige)', bg: '#111', label: slug?.toUpperCase() }

  const CardLink = ({ children }) => newTab
    ? <a href={link} target="_blank" rel="noopener noreferrer" style={{ display: 'block' }}>{children}</a>
    : <Link to={link} style={{ display: 'block' }}>{children}</Link>

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ delay: index * 0.12, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <CardLink>
        <div style={{
          position: 'relative', overflow: 'hidden',
          background: style.bg,
          aspectRatio: tall ? '3/4' : '4/3',
          cursor: 'pointer',
        }}>
          {/* Animated border */}
          <motion.div
            animate={{ opacity: hovered ? 1 : 0 }}
            transition={{ duration: 0.3 }}
            style={{
              position: 'absolute', inset: 1,
              border: `1px solid ${style.accent}22`,
              zIndex: 2, pointerEvents: 'none',
            }}
          />

          {/* Giant letter watermark */}
          <motion.div
            animate={{ scale: hovered ? 1.05 : 1, opacity: hovered ? 0.06 : 0.04 }}
            transition={{ duration: 0.6 }}
            style={{
              position: 'absolute', inset: 0, zIndex: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <span style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(100px, 20vw, 220px)', fontWeight: 900,
              color: style.accent, letterSpacing: '-0.05em',
              userSelect: 'none',
            }}>
              {title[0]}
            </span>
          </motion.div>

          {/* Content */}
          <div style={{
            position: 'absolute', inset: 0, zIndex: 3,
            display: 'flex', flexDirection: 'column',
            justifyContent: 'flex-end', padding: 32,
          }}>
            <p style={{ color: style.accent, fontSize: 9, fontWeight: 800, letterSpacing: '0.22em', marginBottom: 10 }}>
              {style.label}
            </p>
            <h3 style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(24px, 4vw, 38px)', fontWeight: 900,
              letterSpacing: '0.03em', color: '#fff',
              textTransform: 'uppercase', marginBottom: 12, lineHeight: 1,
            }}>
              {title}
            </h3>
            {description && (
              <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 13, lineHeight: 1.6, marginBottom: 20, maxWidth: 280 }}>
                {description}
              </p>
            )}
            <motion.div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <motion.div
                animate={{ width: hovered ? 32 : 18 }}
                transition={{ duration: 0.3 }}
                style={{ height: 1, background: style.accent }}
              />
              <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.16em', color: style.accent }}>
                DÉCOUVRIR
              </span>
            </motion.div>
          </div>
        </div>
      </CardLink>
    </motion.div>
  )
}
