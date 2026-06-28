import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

const CATEGORIES = [
  {
    slug: 'teint',
    label: 'Teint',
    desc: 'Fonds de teint, BB crèmes, poudres, highlighters',
    gradient: 'linear-gradient(145deg, #e7d6bf 0%, #c8a87a 100%)',
    count: 18,
    icon: (
      <svg width="28" height="28" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.2">
        <circle cx="16" cy="13" r="10"/>
        <path d="M8 28 Q16 23 24 28"/>
      </svg>
    ),
  },
  {
    slug: 'levres',
    label: 'Lèvres',
    desc: 'Rouges à lèvres, gloss, lip liners, baumes',
    gradient: 'linear-gradient(145deg, #c8797f 0%, #7a1e2a 100%)',
    count: 24,
    icon: (
      <svg width="28" height="28" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.2">
        <path d="M4 16 Q8 10 16 10 Q24 10 28 16 Q24 24 16 24 Q8 24 4 16Z"/>
        <path d="M4 16 Q10 19 16 16 Q22 19 28 16"/>
      </svg>
    ),
  },
  {
    slug: 'yeux',
    label: 'Yeux',
    desc: 'Mascaras, eye-liners, fards à paupières, crayons',
    gradient: 'linear-gradient(145deg, #3a3040 0%, #1a1020 100%)',
    count: 31,
    icon: (
      <svg width="28" height="28" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.2">
        <path d="M4 16 Q10 8 16 8 Q22 8 28 16 Q22 24 16 24 Q10 24 4 16Z"/>
        <circle cx="16" cy="16" r="5"/>
      </svg>
    ),
  },
  {
    slug: 'accessoires',
    label: 'Accessoires',
    desc: 'Pinceaux, éponges, fixateurs, démaquillants',
    gradient: 'linear-gradient(145deg, #d4c5a9 0%, #8a7a5a 100%)',
    count: 12,
    icon: (
      <svg width="28" height="28" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.2">
        <rect x="14" y="4" width="4" height="18" rx="2"/>
        <ellipse cx="16" cy="8" rx="8" ry="5"/>
        <path d="M8 22 Q16 26 24 22"/>
      </svg>
    ),
  },
]

export default function MakeupCategories() {
  return (
    <section style={{ background: '#f7f1e8', padding: '96px 0' }}>
      <div style={{ maxWidth: 1320, margin: '0 auto', padding: '0 24px' }}>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ marginBottom: 52 }}
        >
          <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.22em', color: '#c9a45c', marginBottom: 12 }}>
            UNIVERS
          </p>
          <h2 className="makeup-section-title" style={{ margin: 0, color: '#090807' }}>
            Nos catégories
          </h2>
        </motion.div>

        <div className="makeup-categories-grid">
          {CATEGORIES.map((cat, i) => (
            <motion.div
              key={cat.slug}
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ delay: i * 0.1, duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
            >
              <Link
                to={`/boutique?categorie=maquillage&sous-categorie=${cat.slug}`}
                className="makeup-category-card"
                style={{ textDecoration: 'none' }}
              >
                {/* Background gradient */}
                <div style={{
                  position: 'absolute', inset: 0,
                  background: cat.gradient,
                  transition: 'transform 0.6s ease',
                }} className="makeup-category-bg" />

                {/* Content */}
                <div style={{
                  position: 'relative', zIndex: 1,
                  padding: '32px 28px',
                  display: 'flex', flexDirection: 'column',
                  height: '100%',
                }}>
                  <span style={{ color: 'rgba(255,255,255,0.8)', marginBottom: 'auto' }}>
                    {cat.icon}
                  </span>

                  <div style={{ marginTop: 60 }}>
                    <p style={{
                      fontSize: 10, fontWeight: 800, letterSpacing: '0.2em',
                      color: 'rgba(255,255,255,0.5)', marginBottom: 8,
                    }}>
                      {cat.count} PRODUITS
                    </p>
                    <h3 style={{
                      fontFamily: '"Playfair Display", Georgia, serif',
                      fontSize: 'clamp(22px, 3vw, 32px)',
                      fontWeight: 500, color: '#fff',
                      margin: '0 0 10px', lineHeight: 1.1,
                    }}>
                      {cat.label}
                    </h3>
                    <p style={{
                      fontSize: 12, color: 'rgba(255,255,255,0.6)',
                      lineHeight: 1.6, margin: 0,
                    }}>
                      {cat.desc}
                    </p>
                  </div>

                  {/* Arrow */}
                  <div style={{
                    marginTop: 24, width: 36, height: 36, borderRadius: '50%',
                    background: 'rgba(255,255,255,0.15)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    transition: 'background 0.2s, transform 0.2s',
                  }} className="makeup-category-arrow">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="white" strokeWidth="2">
                      <path d="M3 8h10M9 4l4 4-4 4"/>
                    </svg>
                  </div>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>

      <style>{`
        .makeup-categories-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 20px;
        }
        .makeup-category-card {
          position: relative;
          overflow: hidden;
          aspect-ratio: 0.72;
          display: block;
          border-radius: 4px;
        }
        .makeup-category-card:hover .makeup-category-bg {
          transform: scale(1.06);
        }
        .makeup-category-card:hover .makeup-category-arrow {
          background: rgba(255,255,255,0.28) !important;
          transform: translateX(4px);
        }
        @media (max-width: 900px) {
          .makeup-categories-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 480px) {
          .makeup-categories-grid { grid-template-columns: 1fr; }
          .makeup-category-card { aspect-ratio: 1.5; }
        }
      `}</style>
    </section>
  )
}
