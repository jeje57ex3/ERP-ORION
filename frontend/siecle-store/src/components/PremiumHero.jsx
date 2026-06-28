import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion, useScroll, useTransform } from 'framer-motion'

export default function PremiumHero({ title, slogan, subtitle, primaryBtn, primaryLink, secondaryBtn, secondaryLink, onScrollTarget }) {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })
  const y      = useTransform(scrollYProgress, [0, 1], ['0%', '22%'])
  const opacity = useTransform(scrollYProgress, [0, 0.6], [1, 0])

  const scrollDown = () => {
    if (onScrollTarget) {
      document.getElementById(onScrollTarget)?.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <section ref={ref} style={{
      position: 'relative', height: '100vh', minHeight: 680,
      overflow: 'hidden', background: '#000',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {/* Grain overlay */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 1,
        backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\' opacity=\'0.03\'/%3E%3C/svg%3E")',
        backgroundSize: '200px 200px', opacity: 0.4,
      }} />

      {/* Vertical accent lines */}
      <div style={{ position: 'absolute', top: 0, left: '20%', width: 1, height: '35%', background: 'linear-gradient(to bottom, transparent, rgba(216,199,163,0.2))', zIndex: 1 }} />
      <div style={{ position: 'absolute', bottom: 0, right: '20%', width: 1, height: '35%', background: 'linear-gradient(to top, transparent, rgba(216,199,163,0.2))', zIndex: 1 }} />

      {/* Content */}
      <motion.div style={{ y, opacity, zIndex: 2, textAlign: 'center', padding: '0 24px', maxWidth: 900, margin: '0 auto' }}>
        <motion.p
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.3, duration: 0.7 } }}
          style={{ color: 'var(--siecle-beige)', fontSize: 10, fontWeight: 800, letterSpacing: '0.35em', marginBottom: 28 }}
        >
          {slogan}
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.5, duration: 0.9, ease: [0.22, 1, 0.36, 1] } }}
          style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 'clamp(60px, 12vw, 140px)',
            fontWeight: 900, lineHeight: 0.88,
            letterSpacing: '-0.03em', color: '#fff',
            marginBottom: 28,
          }}
        >
          {title}
        </motion.h1>

        {subtitle && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { delay: 0.85, duration: 0.8 } }}
            style={{ color: 'rgba(255,255,255,0.45)', fontSize: 15, lineHeight: 1.8, maxWidth: 480, margin: '0 auto 44px' }}
          >
            {subtitle}
          </motion.p>
        )}

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 1.1, duration: 0.6 } }}
          style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap' }}
        >
          {primaryBtn && onScrollTarget && (
            <button onClick={scrollDown} style={{
              padding: '14px 36px', background: 'transparent',
              border: '1px solid rgba(255,255,255,0.25)', color: '#fff',
              fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', cursor: 'pointer',
              transition: 'all 0.25s',
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--siecle-beige)'; e.currentTarget.style.color = 'var(--siecle-beige)' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.25)'; e.currentTarget.style.color = '#fff' }}
            >
              {primaryBtn}
            </button>
          )}
          {primaryBtn && primaryLink && (
            <Link to={primaryLink} style={{
              padding: '14px 36px', background: 'transparent',
              border: '1px solid rgba(255,255,255,0.25)', color: '#fff',
              fontSize: 11, fontWeight: 700, letterSpacing: '0.16em',
              display: 'inline-block', textAlign: 'center',
            }}>
              {primaryBtn}
            </Link>
          )}
          {secondaryBtn && secondaryLink && (
            <Link to={secondaryLink} style={{
              padding: '14px 36px', background: 'var(--siecle-beige)', color: '#000',
              fontSize: 11, fontWeight: 800, letterSpacing: '0.16em',
              display: 'inline-block', textAlign: 'center',
            }}>
              {secondaryBtn}
            </Link>
          )}
        </motion.div>
      </motion.div>

      {/* Scroll indicator */}
      <motion.div
        animate={{ y: [0, 8, 0] }}
        transition={{ repeat: Infinity, duration: 2.2, ease: 'easeInOut' }}
        style={{
          position: 'absolute', bottom: 36, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, zIndex: 2,
          cursor: 'pointer',
        }}
        onClick={scrollDown}
      >
        <span style={{ fontSize: 9, letterSpacing: '0.25em', color: 'rgba(255,255,255,0.25)' }}>SCROLL</span>
        <div style={{ width: 1, height: 36, background: 'linear-gradient(to bottom, rgba(255,255,255,0.2), transparent)' }} />
      </motion.div>
    </section>
  )
}
