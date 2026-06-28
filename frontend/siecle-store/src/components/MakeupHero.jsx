import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

// Elegant gradient placeholder for hero image
function HeroImagePlaceholder() {
  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'linear-gradient(160deg, #e7d6bf 0%, #c8ad8b 40%, #4a3426 100%)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Abstract face suggestion */}
      <div style={{ position: 'absolute', inset: 0 }}>
        <div style={{
          position: 'absolute', top: '10%', left: '20%', right: '20%', bottom: '5%',
          background: 'linear-gradient(180deg, #c8ad8b 0%, #4a3426 80%)',
          borderRadius: '50% 50% 50% 50% / 40% 40% 60% 60%',
          opacity: 0.35,
        }} />
        <div style={{
          position: 'absolute', top: '15%', left: '30%', right: '30%',
          height: '45%',
          background: 'linear-gradient(180deg, #e0c9a8 0%, #b89870 100%)',
          borderRadius: '50% 50% 45% 45% / 55% 55% 45% 45%',
          opacity: 0.6,
        }} />
      </div>

      {/* Grain texture */}
      <div style={{
        position: 'absolute', inset: 0,
        backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\' opacity=\'0.04\'/%3E%3C/svg%3E")',
        backgroundSize: '200px 200px',
      }} />

      {/* Gold accent */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, height: '30%',
        background: 'linear-gradient(to top, rgba(201,164,92,0.15), transparent)',
      }} />
    </div>
  )
}

export default function MakeupHero() {
  return (
    <section style={{
      minHeight: '90vh',
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      overflow: 'hidden',
    }}
      className="makeup-hero-grid"
    >
      {/* Left — text */}
      <div style={{
        background: '#f7f1e8',
        display: 'flex', flexDirection: 'column',
        justifyContent: 'center',
        padding: 'clamp(48px, 8vw, 100px) clamp(32px, 6vw, 80px)',
      }}>
        <motion.span
          className="makeup-eyebrow"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          Collection SIÈCLE
        </motion.span>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          style={{
            fontFamily: '"Playfair Display", "Cormorant Garamond", Georgia, serif',
            fontSize: 'clamp(40px, 5.5vw, 78px)',
            fontWeight: 500, lineHeight: 1.02,
            letterSpacing: '-0.03em',
            color: '#090807',
            margin: '0 0 28px',
          }}
        >
          La beauté<br />dans le<br />détail.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: 16, lineHeight: 1.8,
            color: '#86796e',
            maxWidth: 400, marginBottom: 44,
          }}
        >
          Un maquillage haut de gamme, pensé pour révéler l'allure avec élégance, précision et intensité.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.75 }}
          style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}
        >
          <Link to="/boutique?categorie=maquillage" className="makeup-btn">
            Découvrir la collection
          </Link>
          <Link to="/boutique?categorie=maquillage&popular=true" style={{
            display: 'inline-flex', alignItems: 'center',
            gap: 8, fontSize: 13, fontWeight: 600,
            color: '#4a3426', textDecoration: 'none',
            paddingTop: 14, transition: 'gap 0.2s',
          }}
            onMouseEnter={e => e.currentTarget.style.gap = '14px'}
            onMouseLeave={e => e.currentTarget.style.gap = '8px'}
          >
            Voir les best-sellers →
          </Link>
        </motion.div>
      </div>

      {/* Right — image */}
      <motion.div
        initial={{ opacity: 0, scale: 1.03 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
        style={{ position: 'relative', overflow: 'hidden', minHeight: 500 }}
      >
        <HeroImagePlaceholder />

        {/* Floating badge */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.9 }}
          style={{
            position: 'absolute', bottom: 40, left: 40,
            background: 'rgba(247,241,232,0.92)',
            backdropFilter: 'blur(10px)',
            padding: '18px 24px',
            border: '1px solid rgba(201,164,92,0.3)',
          }}
        >
          <p style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.2em', color: '#c9a45c', margin: 0 }}>
            CRUELTY-FREE
          </p>
          <p style={{ fontSize: 12, color: '#86796e', margin: '4px 0 0', lineHeight: 1.5 }}>
            Formules vegan & éthiques
          </p>
        </motion.div>
      </motion.div>

      <style>{`
        @media (max-width: 768px) {
          .makeup-hero-grid { grid-template-columns: 1fr !important; }
          .makeup-hero-grid > div:first-child { padding: 48px 24px !important; }
        }
      `}</style>
    </section>
  )
}
