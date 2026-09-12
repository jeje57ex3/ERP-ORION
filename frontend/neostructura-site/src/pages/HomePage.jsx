import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { motion } from 'framer-motion'
import Reveal from '../components/Reveal'
import StatCounter from '../components/StatCounter'
import { METIERS } from '../data/metiers'

// Chiffres structurels réels (nombre de domaines gérés par le configurateur,
// disponibilité de l'outil en ligne) — jamais de statistique de performance
// inventée (satisfaction, nombre de chantiers...) sans donnée Orion pour
// l'étayer.
const STATS = [
  { value: 3, suffix: '', label: "Domaines d'expertise" },
  { value: 24, suffix: '/7', label: 'Configurateur en ligne' },
  { value: 100, suffix: '%', label: 'Estimations transparentes' },
]

const SCALES = [
  {
    tag: 'INTERVENTION', title: 'Le petit dépannage',
    items: ['Petit dépannage', 'Installation ponctuelle', 'Remplacement'],
  },
  {
    tag: 'PROJET', title: 'Le projet ciblé',
    items: ['Rénovation électrique', 'Réseau informatique', 'Mise en conformité'],
  },
  {
    tag: 'CHANTIER', title: 'Le bâtiment complet',
    items: ['Maison complète', 'Appartement', 'Commerce', 'Bureaux'],
  },
  {
    tag: 'PROJET COMPLEXE', title: 'Le multi-lots',
    items: ['Électricité + réseau', 'BTP + technique', 'Maintenance planifiée'],
  },
]

const STEPS = [
  { n: '01', title: 'Vous décrivez', text: 'Un problème, un projet ou un chantier complet — dites-nous simplement ce dont vous avez besoin.' },
  { n: '02', title: 'Nous qualifions', text: 'Notre configurateur pose uniquement les questions utiles à votre situation.' },
  { n: '03', title: 'Nous estimons', text: 'Matériel, main-d’œuvre, déplacement : une fourchette claire, calculée sans marge cachée.' },
  { n: '04', title: 'Nous validons', text: 'Un technicien vérifie chaque dossier avant tout engagement — visite si nécessaire.' },
  { n: '05', title: 'Nous intervenons', text: 'Une équipe qualifiée réalise les travaux, avec un suivi transparent du chantier.' },
  { n: '06', title: 'Nous suivons', text: 'Documents, réception des travaux et garanties centralisés à un seul endroit.' },
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
            <div className="neo-eyebrow">NÉOSTRUCTURA — Construire durablement, ensemble.</div>
            <h1 style={{ fontSize: 'clamp(38px, 6vw, 66px)', marginBottom: 24 }}>
              Vos projets techniques,<br />exécutés avec précision.
            </h1>
            <p style={{ fontSize: 15, fontWeight: 700, letterSpacing: '0.04em', color: 'var(--text)', marginBottom: 18 }}>
              ÉLECTRICITÉ&nbsp;• BTP&nbsp;• RÉSEAUX&nbsp;• DOMOTIQUE&nbsp;• MAINTENANCE
            </p>
            <p style={{ fontSize: 18, lineHeight: 1.7, color: 'var(--text-muted)', maxWidth: 560, marginBottom: 32 }}>
              Du petit dépannage au chantier complet, NÉOSTRUCTURA qualifie, chiffre et
              suit votre projet avec un seul interlocuteur — et un configurateur qui
              s'adapte à ce que vous savez déjà, ou non.
            </p>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
              <Link to="/configurateur" className="neo-btn neo-btn-primary neo-btn-lg">
                Configurer mon projet
              </Link>
              <Link to="/contact" className="neo-btn neo-btn-outline neo-btn-lg">
                Parler à un expert
              </Link>
            </div>
            <p style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
              ✓ Estimation indicative en quelques minutes — validation technique avant tout devis définitif.
            </p>
          </motion.div>

          <Reveal delay={0.2} style={{
            marginTop: 72, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24,
            paddingTop: 40, borderTop: '1px solid var(--border)', maxWidth: 620,
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
                <Link to="/nos-metiers" className="neo-card neo-hover-arrow" style={{
                  display: 'block', padding: 32, height: '100%',
                }}>
                  <div style={{ fontSize: 30, marginBottom: 18 }}>{m.icon}</div>
                  <h3 style={{ fontSize: 18, marginBottom: 10 }}>{m.name}</h3>
                  <p style={{ fontSize: 14, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 18 }}>{m.short}</p>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)' }}>
                    En savoir plus <span className="neo-arrow">→</span>
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
            <div className="neo-eyebrow">Pour tous les projets</div>
            <h2 style={{ fontSize: 'clamp(26px, 3.4vw, 40px)', marginBottom: 16 }}>
              Du petit dépannage au chantier complet.
            </h2>
            <p style={{ fontSize: 15.5, color: 'var(--text-muted)', lineHeight: 1.7 }}>
              NÉOSTRUCTURA adapte son intervention à votre besoin, à votre bâtiment et à
              votre niveau de projet.
            </p>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 20 }} id="neo-scales-grid">
            {SCALES.map((s, i) => (
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
            <div className="neo-eyebrow">Notre méthode</div>
            <h2 style={{ fontSize: 'clamp(26px, 3.4vw, 40px)' }}>De la demande à la livraison.</h2>
          </Reveal>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 32 }} id="neo-steps-grid">
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
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Link to="/contact" className="neo-btn neo-btn-lg" style={{ background: 'var(--surface-brand-fg)', color: 'var(--surface-brand)' }}>
                Contacter NÉOSTRUCTURA
              </Link>
              <Link to="/realisations" className="neo-btn neo-btn-lg neo-btn-outline" style={{ borderColor: 'rgba(247,247,244,0.4)', color: 'var(--surface-brand-fg)' }}>
                Voir nos réalisations
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
