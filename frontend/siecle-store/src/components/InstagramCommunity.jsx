import { motion } from 'framer-motion'

const POSTS = [
  { gradient: 'linear-gradient(135deg, #e7d6bf 0%, #c8a87a 60%, #8a6a4a 100%)' },
  { gradient: 'linear-gradient(135deg, #c87a7a 0%, #8a3a3a 60%, #4a1a1a 100%)' },
  { gradient: 'linear-gradient(135deg, #4a3040 0%, #3a1f30 60%, #1a0a15 100%)' },
  { gradient: 'linear-gradient(135deg, #e0c9a8 0%, #b89870 60%, #7a5c3a 100%)' },
  { gradient: 'linear-gradient(135deg, #c9a45c 0%, #8a6a2a 60%, #4a3a10 100%)' },
  { gradient: 'linear-gradient(135deg, #d4c0a0 0%, #a08060 60%, #6a4a30 100%)' },
]

function InstagramIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5"/>
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/>
      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/>
    </svg>
  )
}

export default function InstagramCommunity() {
  return (
    <section style={{ background: '#090807', padding: '96px 0' }}>
      <div style={{ maxWidth: 1320, margin: '0 auto', padding: '0 24px' }}>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ textAlign: 'center', marginBottom: 56 }}
        >
          <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.25em', color: '#c9a45c', marginBottom: 14 }}>
            COMMUNAUTÉ
          </p>
          <h2 style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(32px, 5vw, 56px)',
            fontWeight: 500, color: '#f7f1e8',
            letterSpacing: '-0.02em', lineHeight: 1.05,
            margin: '0 0 16px',
          }}>
            #SiècleMaquillage
          </h2>
          <p style={{ fontSize: 14, color: 'rgba(247,241,232,0.45)', maxWidth: 440, margin: '0 auto' }}>
            Rejoignez notre communauté et partagez vos looks avec le hashtag <strong style={{ color: '#c9a45c' }}>#SiècleMaquillage</strong>
          </p>
        </motion.div>

        {/* Grid */}
        <div className="makeup-instagram-grid">
          {POSTS.map((post, i) => (
            <motion.a
              key={i}
              href="https://instagram.com"
              target="_blank"
              rel="noopener noreferrer"
              initial={{ opacity: 0, scale: 0.96 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ delay: i * 0.07, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="makeup-instagram-cell"
              style={{ background: post.gradient }}
            >
              {/* Hover overlay */}
              <div className="makeup-instagram-overlay">
                <span style={{ color: 'var(--siecle-white)' }}>
                  <InstagramIcon />
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 700, letterSpacing: '0.12em',
                  color: 'rgba(241,237,229,0.9)',
                }}>
                  Voir sur Instagram
                </span>
              </div>
            </motion.a>
          ))}
        </div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          style={{ textAlign: 'center', marginTop: 48 }}
        >
          <a
            href="https://instagram.com"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 10,
              fontSize: 13, fontWeight: 700, letterSpacing: '0.1em',
              color: '#c9a45c', textDecoration: 'none',
              border: '1px solid rgba(201,164,92,0.4)',
              padding: '14px 28px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(201,164,92,0.1)'
              e.currentTarget.style.borderColor = '#c9a45c'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.borderColor = 'rgba(201,164,92,0.4)'
            }}
          >
            <InstagramIcon />
            Suivre @SiècleMaquillage
          </a>
        </motion.div>
      </div>

      <style>{`
        .makeup-instagram-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
        }
        .makeup-instagram-cell {
          position: relative;
          aspect-ratio: 1;
          overflow: hidden;
          cursor: pointer;
        }
        .makeup-instagram-overlay {
          position: absolute; inset: 0;
          display: flex; flex-direction: column;
          align-items: center; justify-content: center;
          gap: 10px;
          background: rgba(9,8,7,0);
          transition: background 0.3s;
          opacity: 0;
          transition: opacity 0.3s;
        }
        .makeup-instagram-cell:hover .makeup-instagram-overlay {
          opacity: 1;
          background: rgba(9,8,7,0.55);
        }
        @media (max-width: 600px) {
          .makeup-instagram-grid { grid-template-columns: repeat(2, 1fr); }
        }
      `}</style>
    </section>
  )
}
