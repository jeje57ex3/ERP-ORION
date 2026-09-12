import { useState, useMemo } from 'react'
import { Helmet } from 'react-helmet-async'
import Reveal from '../components/Reveal'
import { useLanguage } from '../i18n/LanguageContext'
import { REALISATIONS } from '../data/realisations'

export default function RealisationsPage() {
  const { dict } = useLanguage()
  const t = dict.realisationsPage
  const [filter, setFilter] = useState(t.filterAll)

  const items = useMemo(() => REALISATIONS.map(r => ({
    ...r,
    category: dict.metiersContent[r.categorySlug]?.name || r.categorySlug,
    ...dict.realisationsContent[r.id],
  })), [dict])

  const categories = useMemo(() => [t.filterAll, ...new Set(items.map(r => r.category))], [items, t.filterAll])
  const filtered = filter === t.filterAll ? items : items.filter(r => r.category === filter)

  return (
    <>
      <Helmet><title>Réalisations — NÉOSTRUCTURA</title></Helmet>

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

      <section className="neo-section" style={{ paddingTop: 8 }}>
        <div className="neo-container">
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 40 }}>
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setFilter(cat)}
                className={filter === cat ? 'neo-btn neo-btn-primary' : 'neo-btn neo-btn-outline'}
                style={{ padding: '9px 18px', fontSize: 13 }}
              >
                {cat}
              </button>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24 }} id="neo-real-grid">
            {filtered.map((r, i) => (
              <Reveal key={r.id} delay={(i % 3) * 0.06} className="neo-card" style={{ overflow: 'hidden' }}>
                <div style={{
                  aspectRatio: '4/3',
                  background: 'linear-gradient(150deg, var(--neo-green) 0%, var(--neo-dark) 100%)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <span style={{
                    fontFamily: 'var(--font-display)', fontSize: 44, fontWeight: 600,
                    color: 'rgba(247,247,244,0.16)',
                  }}>N</span>
                </div>
                <div style={{ padding: 24 }}>
                  <span className="neo-badge" style={{ marginBottom: 12 }}>{r.category}</span>
                  <h3 style={{ fontSize: 17, margin: '10px 0 8px' }}>{r.title}</h3>
                  <p style={{ fontSize: 13.5, color: 'var(--text-muted)' }}>
                    {r.location} · {r.duration}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <style>{`
        @media (max-width: 900px) { #neo-real-grid { grid-template-columns: repeat(2, 1fr) !important; } }
        @media (max-width: 560px) { #neo-real-grid { grid-template-columns: 1fr !important; } }
      `}</style>
    </>
  )
}
