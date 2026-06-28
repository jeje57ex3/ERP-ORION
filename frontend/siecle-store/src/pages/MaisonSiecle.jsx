import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { fadeUp, slideLeft, slideRight, staggerContainer } from '../utils/animations'
import PageTransition from '../components/PageTransition'

const UNIVERS = [
  { label: 'Vêtements', desc: 'Silhouettes propres. Matières douces.',   to: '/vetements', letter: 'V' },
  { label: 'Montres',   desc: 'Design minimaliste. Signal d\'identité.',  to: '/montres',   letter: 'M' },
  { label: 'Maquillage',desc: 'Formules douces. Toutes les carnations.', to: '/maquillage', letter: 'B', newTab: true },
]

const VALEURS = [
  { title: 'Inclusivité',  body: 'La classe n\'a pas de taille, pas de genre imposé, pas de silhouette unique. Nos pièces s\'adaptent.' },
  { title: 'Matières',     body: 'Chaque tissu est choisi pour sa qualité, son toucher et sa durabilité. Rien n\'est laissé au hasard.' },
  { title: 'Minimalisme',  body: 'Pas de superflu. Chaque détail a une raison d\'être. Le vide fait partie du design.' },
]

export default function MaisonSiecle() {
  return (
    <PageTransition>
      <div style={{ background: '#000', color: '#fff', overflowX: 'hidden' }}>

        {/* ── Hero ── */}
        <section style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '120px 24px 80px', textAlign: 'center', position: 'relative' }}>
          <motion.p
            variants={fadeUp} initial="hidden" animate="visible"
            style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.3em', color: 'var(--siecle-beige)', marginBottom: 28 }}
          >
            MAISON SIÈCLE
          </motion.p>
          <motion.h1
            variants={fadeUp} initial="hidden" animate="visible" transition={{ delay: 0.1 }}
            style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(48px, 10vw, 120px)',
              fontWeight: 900, lineHeight: 0.9,
              letterSpacing: '-0.02em',
              marginBottom: 48, maxWidth: 900,
            }}
          >
            UNE VISION<br />DU STYLE.
          </motion.h1>
          <motion.p
            variants={fadeUp} initial="hidden" animate="visible" transition={{ delay: 0.2 }}
            style={{ color: 'rgba(255,255,255,0.45)', fontSize: 16, lineHeight: 1.8, maxWidth: 480 }}
          >
            Une vision du style, du corps et du détail.
          </motion.p>
          {/* Scroll indicator */}
          <motion.div
            animate={{ y: [0, 8, 0] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
            style={{ position: 'absolute', bottom: 40, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}
          >
            <div style={{ width: 1, height: 40, background: 'rgba(255,255,255,0.2)' }} />
            <p style={{ fontSize: 9, letterSpacing: '0.2em', color: 'rgba(255,255,255,0.3)' }}>DÉFILER</p>
          </motion.div>
        </section>

        {/* ── Manifeste ── */}
        <section style={{ padding: '100px 24px', maxWidth: 900, margin: '0 auto', textAlign: 'center' }}>
          <motion.blockquote
            variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}
            style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(20px, 3vw, 32px)', fontWeight: 900, lineHeight: 1.4, letterSpacing: '0.02em', fontStyle: 'normal', margin: 0 }}
          >
            SIÈCLE est née d'une idée simple :<br />
            la classe n'a pas de taille, pas de genre<br />
            imposé, pas de silhouette unique.
          </motion.blockquote>
          <motion.div
            variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}
            style={{ marginTop: 48 }}
          >
            <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 15, lineHeight: 1.9, maxWidth: 640, margin: '0 auto' }}>
              Nous créons des pièces qui imposent une présence, sans jamais effacer celui
              ou celle qui les porte. Chaque collection est pensée pour durer au-delà des saisons.
              Pas de surcharge, pas d'ostentation. Juste la justesse.
            </p>
          </motion.div>
        </section>

        {/* ── Valeurs en 3 colonnes ── */}
        <section style={{ padding: '80px 24px', borderTop: '1px solid rgba(255,255,255,0.06)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <motion.div
              variants={staggerContainer} initial="hidden" whileInView="visible" viewport={{ once: true }}
              style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 60 }}
              className="maison-values-grid"
            >
              {VALEURS.map((v, i) => (
                <motion.div key={v.title} variants={fadeUp} custom={i}>
                  <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.22em', color: 'var(--siecle-beige)', marginBottom: 20 }}>
                    0{i + 1}
                  </p>
                  <h3 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 22, fontWeight: 900, marginBottom: 16 }}>
                    {v.title.toUpperCase()}
                  </h3>
                  <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 14, lineHeight: 1.8 }}>
                    {v.body}
                  </p>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </section>

        {/* ── Univers ── */}
        <section style={{ padding: '100px 24px' }}>
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <motion.div variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }} style={{ textAlign: 'center', marginBottom: 72 }}>
              <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.28em', color: 'var(--siecle-beige)', marginBottom: 14 }}>NOS UNIVERS</p>
              <h2 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(28px, 4vw, 48px)', fontWeight: 900 }}>
                TROIS UNIVERS. UNE VISION.
              </h2>
            </motion.div>

            <motion.div
              variants={staggerContainer} initial="hidden" whileInView="visible" viewport={{ once: true }}
              style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2 }}
              className="maison-universe-grid"
            >
              {UNIVERS.map(u => {
                const content = (
                  <motion.div
                    variants={fadeUp}
                    style={{ background: '#0a0a0a', padding: '80px 40px', textAlign: 'center', position: 'relative', overflow: 'hidden', cursor: 'pointer' }}
                    whileHover={{ background: '#111' }}
                    transition={{ duration: 0.3 }}
                  >
                    <p style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 80, fontWeight: 900, color: 'rgba(255,255,255,0.04)', position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', margin: 0 }}>
                      {u.letter}
                    </p>
                    <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.22em', color: 'var(--siecle-beige)', marginBottom: 14, position: 'relative' }}>
                      {u.label.toUpperCase()}
                    </p>
                    <h3 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 28, fontWeight: 900, marginBottom: 16, position: 'relative' }}>
                      {u.label}
                    </h3>
                    <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 13, position: 'relative' }}>{u.desc}</p>
                    <p style={{ marginTop: 32, fontSize: 10, fontWeight: 700, letterSpacing: '0.16em', color: 'var(--siecle-beige)', position: 'relative' }}>
                      DÉCOUVRIR →
                    </p>
                  </motion.div>
                )
                return u.newTab
                  ? <a key={u.label} href={u.to} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'none', color: 'inherit' }}>{content}</a>
                  : <Link key={u.label} to={u.to} style={{ textDecoration: 'none', color: 'inherit' }}>{content}</Link>
              })}
            </motion.div>
          </div>
        </section>

        {/* ── CTA ── */}
        <section style={{ padding: '120px 24px', textAlign: 'center' }}>
          <motion.div variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>
            <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.28em', color: 'var(--siecle-beige)', marginBottom: 24 }}>
              ENTRER DANS L'UNIVERS
            </p>
            <h2 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(28px, 5vw, 60px)', fontWeight: 900, marginBottom: 40 }}>
              EXPLOREZ LA COLLECTION
            </h2>
            <Link to="/boutique" style={{
              display: 'inline-block', padding: '18px 52px',
              background: 'var(--siecle-beige)', color: '#000',
              fontSize: 11, fontWeight: 800, letterSpacing: '0.18em',
              textDecoration: 'none', transition: 'opacity 0.2s',
            }}
              onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}
            >
              BOUTIQUE SIÈCLE
            </Link>
          </motion.div>
        </section>

        <style>{`
          @media (max-width: 900px) {
            .maison-values-grid   { grid-template-columns: 1fr !important; }
            .maison-universe-grid { grid-template-columns: 1fr !important; }
          }
        `}</style>
      </div>
    </PageTransition>
  )
}
