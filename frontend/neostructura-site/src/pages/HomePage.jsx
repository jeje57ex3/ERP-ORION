import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { motion } from 'framer-motion'
import Reveal from '../components/Reveal'
import StatCounter from '../components/StatCounter'
import { useLanguage } from '../i18n/LanguageContext'
import { METIERS } from '../data/metiers'

const STEP_NUMBERS = ['01', '02', '03', '04', '05', '06']

export default function HomePage() {
  const { dict } = useLanguage()
  const { hero, stats, metiers, scales, method, ctaFinal } = dict.home

  return (
    <>
      <Helmet>
        <title>NÉOSTRUCTURA — Construire durablement, ensemble.</title>
      </Helmet>

      {/* Hero */}
      <section style={{
        position: 'relative', minHeight: '92vh', display: 'flex', alignItems: 'center',
        paddingTop: 'var(--header-h)', overflow: 'hidden',
        background: 'radial-gradient(120% 100% at 100% 0%, var(--bg-subtle), var(--bg) 60%)',
      }}>
        <div className="neo-grid-overlay" aria-hidden="true" />
        <div aria-hidden="true" style={{
          position: 'absolute', top: '18%', right: '6%', width: 340, height: 340,
          borderRadius: '50%', background: 'var(--accent)', opacity: 0.08, filter: 'blur(80px)',
          pointerEvents: 'none',
        }} />

        <div className="neo-container" style={{ position: 'relative', zIndex: 1, padding: '80px 24px' }}>
          <motion.div
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            style={{ maxWidth: 760 }}
          >
            <div className="neo-eyebrow">{hero.eyebrow}</div>
            <h1 style={{ fontSize: 'clamp(38px, 6vw, 66px)', marginBottom: 24 }}>
              {hero.h1a}<br />{hero.h1b}
            </h1>
            <p style={{ fontSize: 15, fontWeight: 700, letterSpacing: '0.04em', color: 'var(--text)', marginBottom: 18 }}>
              {hero.subtitle}
            </p>
            <p style={{ fontSize: 18, lineHeight: 1.7, color: 'var(--text-muted)', maxWidth: 560, marginBottom: 32 }}>
              {hero.paragraph}
            </p>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
              <Link to="/configurateur" className="neo-btn neo-btn-primary neo-btn-lg">
                {hero.ctaPrimary}
              </Link>
              <Link to="/contact" className="neo-btn neo-btn-outline neo-btn-lg">
                {hero.ctaSecondary}
              </Link>
            </div>
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
              {hero.reassurance}
            </p>
          </motion.div>

          <Reveal delay={0.2} style={{
            marginTop: 72, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24,
            paddingTop: 40, borderTop: '1px solid var(--border)', maxWidth: 620,
          }} id="neo-hero-stats">
            {stats.map(s => <StatCounter key={s.label} {...s} />)}
          </Reveal>
        </div>
      </section>

      {/* Nos métiers — teaser */}
      <section className="neo-section">
        <div className="neo-container">
          <Reveal style={{ maxWidth: 620, marginBottom: 56 }}>
            <div className="neo-eyebrow">{metiers.eyebrow}</div>
            <h2 style={{ fontSize: 'clamp(26px, 3.4vw, 40px)' }}>
              {metiers.title}
            </h2>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }} id="neo-metiers-grid">
            {METIERS.map((m, i) => (
              <Reveal key={m.slug} delay={i * 0.06}>
                <Link to="/nos-metiers" className="neo-card neo-hover-arrow" style={{
                  display: 'block', padding: 32, height: '100%',
                }}>
                  <div style={{ fontSize: 30, marginBottom: 18 }}>{m.icon}</div>
                  <h3 style={{ fontSize: 18, marginBottom: 10 }}>{dict.metiersContent[m.slug]?.name}</h3>
                  <p style={{ fontSize: 14, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 18 }}>
                    {dict.metiersContent[m.slug]?.short}
                  </p>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)' }}>
                    {metiers.more} <span className="neo-arrow">→</span>
                  </span>
                </Link>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Pour tous les projets */}
      <section className="neo-section" style={{ background: 'var(--bg-subtle)' }}>
        <div className="neo-container">
          <Reveal style={{ maxWidth: 680, marginBottom: 56 }}>
            <div className="neo-eyebrow">{scales.eyebrow}</div>
            <h2 style={{ fontSize: 'clamp(26px, 3.4vw, 40px)', marginBottom: 16 }}>
              {scales.title}
            </h2>
            <p style={{ fontSize: 15.5, color: 'var(--text-muted)', lineHeight: 1.7 }}>
              {scales.intro}
            </p>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20 }} id="neo-scales-grid">
            {scales.items.map((s, i) => (
              <Reveal key={s.tag} delay={i * 0.06}>
                <div className="neo-card" style={{ padding: 28, height: '100%' }}>
                  <div className="neo-tag-technical" style={{ marginBottom: 16, color: 'var(--accent)', borderColor: 'var(--accent)' }}>
                    {s.tag}
                  </div>
                  <h3 style={{ fontSize: 16, marginBottom: 14 }}>{s.title}</h3>
                  <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {s.items.map(item => (
                      <li key={item} style={{ fontSize: 13.5, color: 'var(--text-muted)', paddingLeft: 14, position: 'relative' }}>
                        <span style={{ position: 'absolute', left: 0, color: 'var(--accent)' }}>—</span>
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Notre méthode */}
      <section className="neo-section">
        <div className="neo-container">
          <Reveal style={{ maxWidth: 620, marginBottom: 56 }}>
            <div className="neo-eyebrow">{method.eyebrow}</div>
            <h2 style={{ fontSize: 'clamp(26px, 3.4vw, 40px)' }}>{method.title}</h2>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 32 }} id="neo-steps-grid">
            {method.steps.map((s, i) => (
              <Reveal key={s.title} delay={i * 0.08}>
                <div style={{
                  fontFamily: 'var(--font-display)', fontSize: 34, color: 'var(--accent)',
                  marginBottom: 14, fontWeight: 600,
                }}>{STEP_NUMBERS[i]}</div>
                <h3 style={{ fontSize: 16, marginBottom: 10 }}>{s.title}</h3>
                <p style={{ fontSize: 14, color: 'var(--text-muted)', lineHeight: 1.65 }}>{s.text}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* CTA final */}
      <section className="neo-section">
        <div className="neo-container">
          <Reveal style={{
            background: 'var(--surface-brand)', color: 'var(--surface-brand-fg)',
            borderRadius: 24, padding: '72px 48px', textAlign: 'center',
          }}>
            <h2 style={{ fontSize: 'clamp(24px, 3.4vw, 36px)', marginBottom: 16 }}>
              {ctaFinal.title}
            </h2>
            <p style={{ opacity: 0.8, maxWidth: 480, margin: '0 auto 32px', fontSize: 15, lineHeight: 1.7 }}>
              {ctaFinal.text}
            </p>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Link to="/contact" className="neo-btn neo-btn-lg" style={{ background: 'var(--surface-brand-fg)', color: 'var(--surface-brand)' }}>
                {ctaFinal.ctaContact}
              </Link>
              <Link to="/realisations" className="neo-btn neo-btn-lg neo-btn-outline" style={{ borderColor: 'rgba(247,247,244,0.4)', color: 'var(--surface-brand-fg)' }}>
                {ctaFinal.ctaRealisations}
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      <style>{`
        @media (max-width: 900px) {
          #neo-hero-stats { grid-template-columns: repeat(3, 1fr) !important; row-gap: 28px !important; }
          #neo-metiers-grid { grid-template-columns: repeat(2, 1fr) !important; }
          #neo-scales-grid { grid-template-columns: repeat(2, 1fr) !important; }
          #neo-steps-grid { grid-template-columns: repeat(2, 1fr) !important; row-gap: 36px !important; }
        }
        @media (max-width: 560px) {
          #neo-hero-stats { grid-template-columns: repeat(3, 1fr) !important; gap: 12px !important; }
          #neo-metiers-grid { grid-template-columns: 1fr !important; }
          #neo-scales-grid { grid-template-columns: 1fr !important; }
          #neo-steps-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  )
}
