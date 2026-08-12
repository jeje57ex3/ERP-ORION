import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { motion, useScroll, useTransform } from 'framer-motion'

export default function PremiumHero({
  topline, slogan, title, subtitle,
  primaryBtn, primaryLink, secondaryBtn, secondaryLink,
  leftLabel, rightLabel, onScrollTarget,
}) {
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
      overflow: 'hidden', background: 'var(--siecle-black)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {/* Grid overlay */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 1,
        backgroundImage: 'linear-gradient(var(--siecle-border) 1px, transparent 1px), linear-gradient(90deg, var(--siecle-border) 1px, transparent 1px)',
        backgroundSize: '64px 64px', opacity: 0.5,
      }} />

      {/* Grain overlay */}
      <div style={{
        position: 'absolute', inset: 0, zIndex: 1,
        backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 200 200\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'n\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.9\' numOctaves=\'4\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23n)\' opacity=\'0.03\'/%3E%3C/svg%3E")',
        backgroundSize: '200px 200px', opacity: 0.4,
      }} />

      {/* Topline */}
      {topline && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { delay: 0.2, duration: 0.7 } }}
          style={{
            position: 'absolute', top: 'calc(var(--header-h) + 20px)', left: 0, right: 0, zIndex: 2,
            textAlign: 'center', color: 'var(--siecle-muted)',
            fontSize: 10, fontWeight: 500, letterSpacing: '0.3em',
          }}
        >
          {topline}
        </motion.p>
      )}

      {/* Vertical side labels */}
      {leftLabel && (
        <div style={{
          position: 'absolute', left: 20, top: '50%', zIndex: 2,
          writingMode: 'vertical-rl', transform: 'translateY(-50%) rotate(180deg)',
          color: 'var(--siecle-muted)', fontSize: 9, fontWeight: 600, letterSpacing: '0.25em',
        }}>
          {leftLabel}
        </div>
      )}
      {rightLabel && (
        <div style={{
          position: 'absolute', right: 20, top: '50%', zIndex: 2,
          writingMode: 'vertical-rl', transform: 'translateY(-50%)',
          color: 'var(--siecle-muted)', fontSize: 9, fontWeight: 600, letterSpacing: '0.25em',
        }}>
          {rightLabel}
        </div>
      )}

      {/* Content */}
      <motion.div style={{ y, opacity, zIndex: 2, textAlign: 'center', padding: '0 24px', maxWidth: 900, margin: '0 auto' }}>
        <motion.p
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.3, duration: 0.7 } }}
          style={{ color: 'var(--siecle-beige)', fontSize: 10, fontWeight: 700, letterSpacing: '0.35em', marginBottom: 28 }}
        >
          {slogan}
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.5, duration: 0.9, ease: [0.22, 1, 0.36, 1] } }}
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(60px, 12vw, 140px)',
            fontWeight: 700, lineHeight: 0.88,
            letterSpacing: '-0.03em', color: 'var(--siecle-white)',
            marginBottom: 28,
          }}
        >
          {title}
        </motion.h1>

        {subtitle && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { delay: 0.85, duration: 0.8 } }}
            style={{ color: 'var(--siecle-muted)', fontSize: 15, lineHeight: 1.8, maxWidth: 480, margin: '0 auto 44px' }}
          >
            {subtitle}
          </motion.p>
        )}

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 1.1, duration: 0.6 } }}
          style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap' }}
        >
          {primaryBtn && onScrollTarget && !primaryLink && (
            <button onClick={scrollDown} style={{
              padding: '14px 36px', background: 'transparent',
              border: '1px solid var(--siecle-border-hover)', color: 'var(--siecle-white)',
              fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', cursor: 'pointer',
              transition: 'all 0.25s',
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--siecle-beige)'; e.currentTarget.style.color = 'var(--siecle-beige)' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--siecle-border-hover)'; e.currentTarget.style.color = 'var(--siecle-white)' }}
            >
              {primaryBtn}
            </button>
          )}
          {primaryBtn && primaryLink && (
            <Link to={primaryLink} style={{
              padding: '14px 36px', background: 'var(--siecle-white)', color: 'var(--siecle-black)',
              fontSize: 11, fontWeight: 700, letterSpacing: '0.16em',
              display: 'inline-block', textAlign: 'center',
            }}>
              {primaryBtn} →
            </Link>
          )}
          {secondaryBtn && secondaryLink && (
            <Link to={secondaryLink} style={{
              padding: '14px 36px', background: 'transparent', color: 'var(--siecle-white)',
              border: '1px solid var(--siecle-border-hover)',
              fontSize: 11, fontWeight: 700, letterSpacing: '0.16em',
              display: 'inline-block', textAlign: 'center', transition: 'all 0.25s',
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--siecle-beige)'; e.currentTarget.style.color = 'var(--siecle-beige)' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--siecle-border-hover)'; e.currentTarget.style.color = 'var(--siecle-white)' }}
            >
              {secondaryBtn}
            </Link>
          )}
        </motion.div>
      </motion.div>

      {/* Scroll indicator */}
      {onScrollTarget && (
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
          <span style={{ fontSize: 9, letterSpacing: '0.25em', color: 'var(--siecle-border-hover)' }}>SCROLL</span>
          <div style={{ width: 1, height: 36, background: 'linear-gradient(to bottom, var(--siecle-border-hover), transparent)' }} />
        </motion.div>
      )}
    </section>
  )
}
