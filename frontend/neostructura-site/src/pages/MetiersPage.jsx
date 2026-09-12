import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import Reveal from '../components/Reveal'
import { useLanguage } from '../i18n/LanguageContext'
import { METIERS } from '../data/metiers'

export default function MetiersPage() {
  const { dict } = useLanguage()
  const t = dict.metiersPage
  const [openSlug, setOpenSlug] = useState(METIERS[0].slug)
  const active = METIERS.find(m => m.slug === openSlug)
  const activeContent = dict.metiersContent[openSlug]

  return (
    <>
      <Helmet><title>Nos métiers — NÉOSTRUCTURA</title></Helmet>

      <section style={{ paddingTop: 'calc(var(--header-h) + 64px)', paddingBottom: 32 }}>
        <div className="neo-container">
          <Reveal style={{ maxWidth: 640 }}>
            <div className="neo-eyebrow">{t.eyebrow}</div>
            <h1 style={{ fontSize: 'clamp(30px, 4.6vw, 48px)', marginBottom: 18 }}>
              {t.h1}
            </h1>
            <p style={{ fontSize: 16, color: 'var(--text-muted)', lineHeight: 1.7 }}>
              {t.intro}
            </p>
          </Reveal>
        </div>
      </section>

      <section className="neo-section" style={{ paddingTop: 24 }}>
        <div className="neo-container" style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 40 }} id="neo-metiers-layout">
          {/* Liste des métiers */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {METIERS.map(m => {
              const isActive = m.slug === openSlug
              return (
                <button
                  key={m.slug}
                  onClick={() => setOpenSlug(m.slug)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left',
                    padding: '16px 18px', borderRadius: 12,
                    background: isActive ? 'var(--surface-brand)' : 'var(--bg-elevated)',
                    color: isActive ? 'var(--surface-brand-fg)' : 'var(--text)',
                    border: '1px solid ' + (isActive ? 'transparent' : 'var(--border)'),
                    transition: 'background var(--transition), color var(--transition)',
                  }}
                >
                  <span style={{ fontSize: 22 }}>{m.icon}</span>
                  <span style={{ fontSize: 14.5, fontWeight: 600 }}>{dict.metiersContent[m.slug]?.name}</span>
                </button>
              )
            })}
          </div>

          {/* Détail du métier sélectionné */}
          {active && activeContent && (
            <Reveal key={active.slug} className="neo-card" style={{ padding: 44 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                <span style={{ fontSize: 36 }}>{active.icon}</span>
                <div>
                  <h2 style={{ fontSize: 26 }}>{activeContent.name}</h2>
                  <span className="neo-badge">{activeContent.badge}</span>
                </div>
              </div>

              <p style={{ fontSize: 15.5, lineHeight: 1.75, color: 'var(--text-muted)', marginBottom: 32, maxWidth: 620 }}>
                {activeContent.description}
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, marginBottom: 32 }} id="neo-metier-detail-grid">
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 14 }}>
                    {t.prestations}
                  </div>
                  <ul style={{ display: 'flex', flexDirection: 'column', gap: 10, listStyle: 'none' }}>
                    {activeContent.services.map(s => (
                      <li key={s} style={{ fontSize: 14, display: 'flex', gap: 10, alignItems: 'baseline' }}>
                        <span style={{ color: 'var(--accent)' }}>✓</span>{s}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 14 }}>
                    {t.technologies}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {activeContent.technologies.map(tech => <span key={tech} className="neo-badge">{tech}</span>)}
                  </div>
                </div>
              </div>

              <Link to="/configurateur" className="neo-btn neo-btn-primary">
                {t.ctaPrefix}{activeContent.name}
              </Link>
            </Reveal>
          )}
        </div>
      </section>

      <style>{`
        @media (max-width: 860px) {
          #neo-metiers-layout { grid-template-columns: 1fr !important; }
          #neo-metier-detail-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  )
}
