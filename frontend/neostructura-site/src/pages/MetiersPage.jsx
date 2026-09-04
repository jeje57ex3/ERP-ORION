import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import Reveal from '../components/Reveal'
import { METIERS } from '../data/metiers'

export default function MetiersPage() {
  const [openSlug, setOpenSlug] = useState(METIERS[0].slug)

  return (
    <>
      <Helmet><title>Nos métiers — NÉOSTRUCTURA</title></Helmet>

      <section style={{ paddingTop: 'calc(var(--header-h) + 64px)', paddingBottom: 32 }}>
        <div className="neo-container">
          <Reveal style={{ maxWidth: 640 }}>
            <div className="neo-eyebrow">Nos métiers</div>
            <h1 style={{ fontSize: 'clamp(30px, 4.6vw, 48px)', marginBottom: 18 }}>
              Six expertises techniques, une seule équipe.
            </h1>
            <p style={{ fontSize: 16, color: 'var(--text-muted)', lineHeight: 1.7 }}>
              Électricité, domotique, étanchéité, informatique &amp; réseaux, rénovation et
              maintenance — nous couvrons l'ensemble des besoins techniques de votre bâtiment.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="neo-section" style={{ paddingTop: 24 }}>
        <div className="neo-container" style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 40 }} id="neo-metiers-layout">
          {/* Liste des métiers */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {METIERS.map(m => {
              const active = m.slug === openSlug
              return (
                <button
                  key={m.slug}
                  onClick={() => setOpenSlug(m.slug)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 14, textAlign: 'left',
                    padding: '16px 18px', borderRadius: 12,
                    background: active ? 'var(--surface-brand)' : 'var(--bg-elevated)',
                    color: active ? 'var(--surface-brand-fg)' : 'var(--text)',
                    border: '1px solid ' + (active ? 'transparent' : 'var(--border)'),
                    transition: 'background var(--transition), color var(--transition)',
                  }}
                >
                  <span style={{ fontSize: 22 }}>{m.icon}</span>
                  <span style={{ fontSize: 14.5, fontWeight: 600 }}>{m.name}</span>
                </button>
              )
            })}
          </div>

          {/* Détail du métier sélectionné */}
          {METIERS.filter(m => m.slug === openSlug).map(m => (
            <Reveal key={m.slug} className="neo-card" style={{ padding: 44 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                <span style={{ fontSize: 36 }}>{m.icon}</span>
                <div>
                  <h2 style={{ fontSize: 26 }}>{m.name}</h2>
                  <span className="neo-badge">{m.priceIndicatif}</span>
                </div>
              </div>

              <p style={{ fontSize: 15.5, lineHeight: 1.75, color: 'var(--text-muted)', marginBottom: 32, maxWidth: 620 }}>
                {m.description}
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, marginBottom: 32 }} id="neo-metier-detail-grid">
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 14 }}>
                    Prestations
                  </div>
                  <ul style={{ display: 'flex', flexDirection: 'column', gap: 10, listStyle: 'none' }}>
                    {m.services.map(s => (
                      <li key={s} style={{ fontSize: 14, display: 'flex', gap: 10, alignItems: 'baseline' }}>
                        <span style={{ color: 'var(--accent)' }}>✓</span>{s}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 14 }}>
                    Technologies
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {m.technologies.map(t => <span key={t} className="neo-badge">{t}</span>)}
                  </div>
                </div>
              </div>

              <Link to="/contact" className="neo-btn neo-btn-primary">
                Demander un devis — {m.name}
              </Link>
            </Reveal>
          ))}
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
