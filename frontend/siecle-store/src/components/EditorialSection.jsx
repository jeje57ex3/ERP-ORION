import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'

export default function EditorialSection({ eyebrow, title, text, btnLabel, btnLink, reverse = false, accent = 'var(--siecle-beige)', children }) {
  return (
    <section style={{ padding: '100px 24px', background: '#000' }}>
      <div style={{
        maxWidth: 1200, margin: '0 auto',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 80, alignItems: 'center',
        direction: reverse ? 'rtl' : 'ltr',
      }}
        className="editorial-grid"
      >
        <motion.div
          style={{ direction: 'ltr' }}
          initial={{ opacity: 0, x: reverse ? 30 : -30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        >
          {eyebrow && (
            <p style={{ color: accent, fontSize: 9, fontWeight: 800, letterSpacing: '0.25em', marginBottom: 16 }}>
              {eyebrow}
            </p>
          )}
          <h2 style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 'clamp(26px, 3.5vw, 42px)', fontWeight: 900,
            letterSpacing: '0.02em', color: '#fff',
            lineHeight: 1.08, marginBottom: 20,
          }}>
            {title}
          </h2>
          {text && (
            <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 14, lineHeight: 1.85, marginBottom: 32, maxWidth: 420 }}>
              {text}
            </p>
          )}
          {btnLabel && btnLink && (
            <Link to={btnLink} style={{
              display: 'inline-block', padding: '13px 30px',
              border: `1px solid ${accent}55`, color: accent,
              fontSize: 10, fontWeight: 700, letterSpacing: '0.16em',
              transition: 'all 0.2s',
            }}>
              {btnLabel}
            </Link>
          )}
        </motion.div>

        <motion.div
          style={{ direction: 'ltr' }}
          initial={{ opacity: 0, scale: 0.96 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        >
          {children}
        </motion.div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .editorial-grid { grid-template-columns: 1fr !important; direction: ltr !important; gap: 40px !important; }
        }
      `}</style>
    </section>
  )
}
