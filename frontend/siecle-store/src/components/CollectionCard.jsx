import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

const COLLECTION_BG = {
  vetements:  'linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%)',
  montres:    'linear-gradient(135deg, #1C1410 0%, #3D2B1F 100%)',
  maquillage: 'linear-gradient(135deg, #1a1218 0%, #2d1f28 100%)',
}

const COLLECTION_ACCENT = {
  vetements:  '#C8B89A',
  montres:    '#D4A76A',
  maquillage: '#C99AAA',
}

export default function CollectionCard({ collection, index = 0 }) {
  const [hovered, setHovered] = useState(false)
  const slug = collection.slug || collection.name?.toLowerCase()
  const accent = COLLECTION_ACCENT[slug] || 'var(--siecle-beige)'
  const bg     = COLLECTION_BG[slug]     || 'linear-gradient(135deg, #111 0%, #222 100%)'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ delay: index * 0.1, duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <Link to={`/shop?category=${slug}`} style={{ display: 'block' }}>
        <div style={{
          position: 'relative', overflow: 'hidden',
          aspectRatio: '4/5', background: bg,
          cursor: 'pointer',
        }}>
          {collection.image ? (
            <img src={collection.image} alt={collection.name}
              style={{
                width: '100%', height: '100%', objectFit: 'cover',
                transition: 'transform 0.7s ease',
                transform: hovered ? 'scale(1.06)' : 'scale(1)',
              }}
            />
          ) : (
            <div style={{
              width: '100%', height: '100%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <span style={{
                fontSize: 64, opacity: 0.08,
                fontFamily: 'Montserrat, sans-serif', fontWeight: 900,
                letterSpacing: '0.05em', color: '#fff',
              }}>
                {collection.name?.toUpperCase()}
              </span>
            </div>
          )}

          {/* Overlay gradient */}
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 50%)',
            transition: 'opacity 0.3s',
            opacity: hovered ? 1 : 0.6,
          }} />

          {/* Content */}
          <div style={{
            position: 'absolute', bottom: 24, left: 24, right: 24,
          }}>
            <p style={{ color: accent, fontSize: 10, fontWeight: 800, letterSpacing: '0.16em', marginBottom: 6 }}>
              COLLECTION
            </p>
            <p style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 22, fontWeight: 900,
              letterSpacing: '0.06em', color: '#fff',
              textTransform: 'uppercase',
              marginBottom: 8,
            }}>
              {collection.name}
            </p>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: hovered ? 40 : 24 }}
              transition={{ duration: 0.3 }}
              style={{ height: 1, background: accent }}
            />
          </div>
        </div>
      </Link>
    </motion.div>
  )
}
