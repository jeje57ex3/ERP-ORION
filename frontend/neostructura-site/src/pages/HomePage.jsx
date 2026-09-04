import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { motion } from 'framer-motion'
import Reveal from '../components/Reveal'
import StatCounter from '../components/StatCounter'
import { METIERS } from '../data/metiers'

const STATS = [
  { value: 150, suffix: '+', label: 'Projets réalisés' },
  { value: 98, suffix: '%', label: 'Satisfaction client' },
  { value: 15, suffix: ' ans', label: "D'expérience" },
  { value: 24, suffix: '/7', label: 'Assistance technique' },
]

const STEPS = [
  { n: '01', title: 'Vous décrivez votre projet', text: 'Contactez-nous : électricité, domotique, étanchéité, informatique, rénovation ou maintenance.' },
  { n: '02', title: 'Nous étudions et chiffrons', text: "Notre équipe analyse votre besoin et vous propose une estimation claire, sans engagement." },
  { n: '03', title: 'Nous intervenons', text: 'Une équipe qualifiée réalise les travaux, avec un suivi transparent du chantier.' },
  { n: '04', title: 'Vous suivez la livraison', text: 'Documents, réception des travaux et garanties centralisés à un seul endroit.' },
]

export default function HomePage() {
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
        <div aria-hidden="true" style={{
          position: 'absolute', inset: 0, opacity: 0.05, pointerEvents: 'none',
          backgroundImage: 'linear-gradient(var(--text) 1px, transparent 1px), linear-gradient(90deg, var(--text) 1px, transparent 1px)',
          backgroundSize: '64px 64px',
        }} />

        <div className="neo-container" style={{ position: 'relative', zIndex: 1, padding: '80px 24px' }}>
          <motion.div
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            style={{ maxWidth: 760 }}
          >
            <div className="neo-eyebrow">Électricité · Domotique · Informatique · Étanchéité · Rénovation</div>
            <h1 style={{ fontSize: 'clamp(38px, 6vw, 68px)', marginBottom: 24 }}>
              Construire durablement.<br />Ensemble.
            </h1>
            <p style={{ fontSize: 18, lineHeight: 1.7, color: 'var(--text-muted)', maxWidth: 560, marginBottom: 40 }}>
              NÉOSTRUCTURA accompagne vos projets en électricité, construction, domotique
              et solutions techniques — un interlocuteur unique du premier contact à la
              livraison finale.
            </p>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <Link to="/contact" className="neo-btn neo-btn-primary neo-btn-lg">
                Démarrer mon projet
              </Link>
              <Link to="/realisations" className="neo-btn neo-btn-outline neo-btn-lg">
                Découvrir nos réalisations
              </Link>
            </div>
          </motion.div>

          <Reveal delay={0.2} style={{
            marginTop: 88, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24,
            paddingTop: 40, borderTop: '1px solid var(--border)',
          }} id="neo-hero-stats">
            {STATS.map(s => <StatCounter key={s.label} {...s} />)}
          </Reveal>
        </div>
      </section>

      {/* Nos métiers — teaser */}
      <section className="neo-section">
        <div className="neo-container">
          <Reveal style={{ maxWidth: 620, marginBottom: 56 }}>
            <div className="neo-eyebrow">Nos métiers</div>
            <h2 style={{ fontSize: 'clamp(26px, 3.4vw, 40px)' }}>
              Six expertises, un seul interlocuteur.
            </h2>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }} id="neo-metiers-grid">
            {METIERS.map((m, i) => (
              <Reveal key={m.slug} delay={i * 0.06}>
                <Link to="/nos-metiers" className="neo-card" style={{
                  display: 'block', padding: 32, height: '100%',
                }}>
                  <div style={{ fontSize: 30, marginBottom: 18 }}>{m.icon}</div>
                  <h3 style={{ fontSize: 18, marginBottom: 10 }}>{m.name}</h3>
                  <p style={{ fontSize: 14, color: 'var(--text-muted)', lineHeight: 1.6 }}>{m.short}</p>
                </Link>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Comment ça marche */}
      <section className="neo-section" style={{ background: 'var(--bg-subtle)' }}>
        <div className="neo-container">
          <Reveal style={{ maxWidth: 620, marginBottom: 56 }}>
            <div className="neo-eyebrow">Notre méthode</div>
            <h2 style={{ fontSize: 'clamp(26px, 3.4vw, 40px)' }}>De la demande à la livraison.</h2>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 32 }} id="neo-steps-grid">
            {STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 0.08}>
                <div style={{
                  fontFamily: 'var(--font-display)', fontSize: 34, color: 'var(--accent)',
                  marginBottom: 14, fontWeight: 600,
                }}>{s.n}</div>
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
              Un projet en tête ?
            </h2>
            <p style={{ opacity: 0.8, maxWidth: 480, margin: '0 auto 32px', fontSize: 15, lineHeight: 1.7 }}>
              Parlez-nous de votre besoin — nous vous répondons rapidement avec une
              première estimation.
            </p>
            <Link to="/contact" className="neo-btn neo-btn-lg" style={{ background: 'var(--surface-brand-fg)', color: 'var(--surface-brand)' }}>
              Contacter NÉOSTRUCTURA
            </Link>
          </Reveal>
        </div>
      </section>

      <style>{`
        @media (max-width: 900px) {
          #neo-hero-stats { grid-template-columns: repeat(2, 1fr) !important; row-gap: 28px !important; }
          #neo-metiers-grid { grid-template-columns: repeat(2, 1fr) !important; }
          #neo-steps-grid { grid-template-columns: repeat(2, 1fr) !important; row-gap: 36px !important; }
        }
        @media (max-width: 560px) {
          #neo-metiers-grid { grid-template-columns: 1fr !important; }
          #neo-steps-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  )
}
