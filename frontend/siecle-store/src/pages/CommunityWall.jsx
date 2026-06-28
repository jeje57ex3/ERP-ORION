import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { staggerContainer, fadeUp } from '../utils/animations'
import PageTransition from '../components/PageTransition'

const DEMO_POSTS = [
  { id: 1, user: 'A.M.',  caption: 'Look du soir avec la veste noire SIÈCLE',       universe: 'vetements', likes: 47 },
  { id: 2, user: 'L.K.',  caption: 'Ma montre personnalisée vient d\'arriver 🖤',     universe: 'montres',   likes: 83 },
  { id: 3, user: 'E.V.',  caption: 'Teintes LUNEA sur mon teint mat, magnifique',    universe: 'maquillage',likes: 62 },
  { id: 4, user: 'C.P.',  caption: 'Pack Signature reçu, emballage incroyable',      universe: 'vetements', likes: 38 },
  { id: 5, user: 'M.R.',  caption: 'Mes trois univers SIÈCLE réunis',               universe: 'all',       likes: 121 },
  { id: 6, user: 'N.L.',  caption: 'Fond de teint fluide LUNEA — verdict : 10/10',  universe: 'maquillage',likes: 54 },
]

const UNIVERSE_COLORS = { vetements: '#C8B89A', montres: '#C0A882', maquillage: '#c9957a', all: '#fff' }

export default function CommunityWall() {
  const [posts,  setPosts]  = useState(DEMO_POSTS)
  const [filter, setFilter] = useState('all')
  const [liked,  setLiked]  = useState({})

  const filtered = filter === 'all' ? posts : posts.filter(p => p.universe === filter)

  const like = (id) => {
    setLiked(prev => ({ ...prev, [id]: !prev[id] }))
    setPosts(prev => prev.map(p => p.id === id ? { ...p, likes: p.likes + (liked[id] ? -1 : 1) } : p))
  }

  return (
    <PageTransition>
      <div style={{ background: '#000', color: '#fff', minHeight: '100vh', padding: '80px 24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>

          {/* Header */}
          <motion.div variants={fadeUp} initial="hidden" animate="visible" style={{ textAlign: 'center', marginBottom: 60 }}>
            <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.28em', color: 'var(--siecle-beige)', marginBottom: 14 }}>LA COMMUNAUTÉ</p>
            <h1 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(28px, 4vw, 52px)', fontWeight: 900, marginBottom: 16 }}>
              VOTRE SIÈCLE
            </h1>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14 }}>Les looks de notre communauté, validés par SIÈCLE.</p>
          </motion.div>

          {/* Filtres */}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 48, flexWrap: 'wrap' }}>
            {['all', 'vetements', 'montres', 'maquillage'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  padding: '8px 20px',
                  background: filter === f ? 'var(--siecle-beige)' : 'transparent',
                  color: filter === f ? '#000' : 'rgba(255,255,255,0.4)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  fontSize: 10, fontWeight: 700, letterSpacing: '0.14em',
                  cursor: 'pointer', textTransform: 'uppercase',
                  transition: 'all 0.2s',
                }}
              >
                {f === 'all' ? 'Tous les univers' : f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>

          {/* Grid */}
          <motion.div
            variants={staggerContainer} initial="hidden" animate="visible"
            style={{ columns: '3 280px', gap: 16 }}
          >
            {filtered.map(post => (
              <motion.div key={post.id} variants={fadeUp}
                style={{ breakInside: 'avoid', marginBottom: 16, background: '#0a0a0a', border: '1px solid rgba(255,255,255,0.06)' }}
              >
                {/* Placeholder image */}
                <div style={{
                  background: `linear-gradient(135deg, #111 0%, #1a1a1a 100%)`,
                  aspectRatio: post.id % 3 === 0 ? '4/5' : '1/1',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <p style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 48, fontWeight: 900, color: 'rgba(255,255,255,0.04)' }}>S</p>
                </div>
                <div style={{ padding: '16px 16px 12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <p style={{ fontSize: 11, fontWeight: 700, color: '#fff' }}>{post.user}</p>
                    <span style={{
                      fontSize: 8, fontWeight: 800, letterSpacing: '0.1em', padding: '3px 8px',
                      background: UNIVERSE_COLORS[post.universe] + '18',
                      color: UNIVERSE_COLORS[post.universe],
                      border: `1px solid ${UNIVERSE_COLORS[post.universe]}33`,
                    }}>
                      {post.universe.toUpperCase()}
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.45)', lineHeight: 1.5, marginBottom: 10 }}>{post.caption}</p>
                  <button onClick={() => like(post.id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: liked[post.id] ? 'var(--siecle-beige)' : 'rgba(255,255,255,0.3)', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6, padding: 0 }}>
                    ♥ {post.likes}
                  </button>
                </div>
              </motion.div>
            ))}
          </motion.div>

          {/* CTA upload */}
          <motion.div variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}
            style={{ textAlign: 'center', marginTop: 80, padding: '60px 24px', border: '1px solid rgba(255,255,255,0.06)' }}>
            <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.24em', color: 'var(--siecle-beige)', marginBottom: 16 }}>PARTAGEZ VOTRE LOOK</p>
            <h2 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 28, fontWeight: 900, marginBottom: 16 }}>REJOIGNEZ LA COMMUNAUTÉ</h2>
            <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: 13, marginBottom: 32 }}>
              Postez votre look, gagnez +50 points fidélité si votre post est validé.
            </p>
            <button style={{ padding: '14px 36px', background: 'var(--siecle-beige)', color: '#000', border: 'none', fontSize: 11, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer' }}>
              POSTER UN LOOK
            </button>
          </motion.div>
        </div>
      </div>
    </PageTransition>
  )
}
