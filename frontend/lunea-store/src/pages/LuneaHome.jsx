import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

export default function LuneaHome() {
  useEffect(() => {
    document.title = 'LUNEA — Beauté, rituel, lumière'
  }, [])

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      {/* Hero */}
      <section style={{
        minHeight: '90vh',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        textAlign: 'center',
        padding: '80px 24px',
        background: 'linear-gradient(160deg, var(--color-bg) 0%, var(--color-surface) 100%)',
        position: 'relative', overflow: 'hidden',
      }}>
        {/* Decorative orb */}
        <div style={{
          position: 'absolute', top: '10%', right: '5%',
          width: 400, height: 400, borderRadius: '50%',
          background: 'radial-gradient(circle, var(--color-primary) 0%, transparent 70%)',
          opacity: 0.12, pointerEvents: 'none',
          animation: 'lunea-orb-float 18s ease-in-out infinite',
        }} />

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="lunea-eyebrow"
        >
          Beauté · Rituel · Lumière
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.15 }}
          className="lunea-heading"
          style={{ marginBottom: '1.5rem', maxWidth: 640 }}
        >
          La beauté comme rituel quotidien
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          style={{ fontSize: 16, color: 'var(--color-text-muted)', maxWidth: 520, marginBottom: '2.5rem', lineHeight: 1.8 }}
        >
          LUNEA célèbre la beauté authentique à travers des soins formulés avec soin,
          des teintes pensées pour toutes les carnations.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.45 }}
          style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}
        >
          <Link to="/lunea/boutique/" className="btn-primary" style={{ minWidth: 180, textAlign: 'center' }}>
            Découvrir
          </Link>
          <Link to="/lunea/rituels/" className="btn-outline" style={{ minWidth: 180, textAlign: 'center' }}>
            Nos rituels
          </Link>
        </motion.div>
      </section>

      {/* Categories */}
      <section className="lunea-section">
        <div className="lunea-container">
          <p className="lunea-eyebrow" style={{ textAlign: 'center' }}>Explorer</p>
          <h2 className="lunea-heading" style={{ textAlign: 'center', marginBottom: '3rem' }}>
            Nos univers beauté
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20 }}>
            {[
              { label: 'Soins visage', desc: 'Hydratation, éclat, anti-âge', link: '/lunea/soins/', emoji: '✨' },
              { label: 'Maquillage', desc: 'Teintes naturelles & intenses', link: '/lunea/maquillage/', emoji: '💄' },
              { label: 'Rituels corps', desc: 'Gommages, huiles, bains', link: '/lunea/rituels/', emoji: '🌿' },
              { label: 'Coffrets', desc: 'Cadeaux & sets complets', link: '/lunea/boutique/?type=coffret', emoji: '🎁' },
            ].map(({ label, desc, link, emoji }) => (
              <Link key={label} to={link} style={{ textDecoration: 'none' }}>
                <motion.div
                  whileHover={{ y: -4 }}
                  transition={{ duration: 0.2 }}
                  style={{
                    background: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius)',
                    padding: '2rem 1.5rem',
                    textAlign: 'center',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontSize: 36, marginBottom: 12 }}>{emoji}</div>
                  <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', fontWeight: 400, marginBottom: 8, color: 'var(--color-text)' }}>
                    {label}
                  </h3>
                  <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>{desc}</p>
                </motion.div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <style>{`
        @keyframes lunea-orb-float {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50%       { transform: translate(-20px, 30px) scale(1.08); }
        }
      `}</style>
    </div>
  )
}
