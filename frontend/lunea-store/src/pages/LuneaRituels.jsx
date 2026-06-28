import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

function RoutineCard({ routine }) {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
      style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius)', overflow: 'hidden',
      }}
    >
      {routine.image && (
        <div style={{ aspectRatio: '16/9', overflow: 'hidden' }}>
          <img src={routine.image} alt={routine.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        </div>
      )}
      <div style={{ padding: '1.25rem' }}>
        <p style={{ fontSize: 11, color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
          {routine.steps_count ? `${routine.steps_count} étapes` : 'Rituel'}
        </p>
        <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', marginBottom: 8 }}>{routine.name}</p>
        <p style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.6, marginBottom: 16 }}>
          {routine.description || 'Un rituel beauté conçu pour sublimer votre peau au quotidien.'}
        </p>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {routine.total_price && (
            <span style={{ fontFamily: 'var(--font-heading)', fontSize: '0.95rem', color: 'var(--color-text-muted)' }}>
              À partir de {Number(routine.total_price).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
            </span>
          )}
          <Link to={`/lunea/rituels/${routine.slug}/`} className="btn-outline" style={{ fontSize: 12, padding: '6px 16px' }}>
            Découvrir
          </Link>
        </div>
      </div>
    </motion.div>
  )
}

export default function LuneaRituels() {
  const [routines, setRoutines] = useState([])
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    document.title = 'Rituels corps — LUNEA'
    Promise.all([
      fetch('/api/v1/lunea/routines/').then(r => r.ok ? r.json() : null),
      fetch('/api/v1/lunea/products/?category=rituels').then(r => r.ok ? r.json() : null),
    ]).then(([r, p]) => {
      setRoutines(r?.results ?? r ?? [])
      setProducts(p?.results ?? p ?? [])
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      {/* Hero */}
      <section style={{
        padding: '5rem 24px', textAlign: 'center',
        background: 'linear-gradient(160deg, var(--color-bg) 0%, var(--color-surface) 100%)',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', bottom: '-20%', left: '5%',
          width: 320, height: 320, borderRadius: '50%',
          background: 'radial-gradient(circle, var(--color-primary) 0%, transparent 70%)',
          opacity: 0.08, pointerEvents: 'none',
        }} />
        <p className="lunea-eyebrow">Bien-être</p>
        <h1 className="lunea-heading">Rituels corps</h1>
        <p style={{ fontSize: 15, color: 'var(--color-text-muted)', maxWidth: 500, margin: '1rem auto 0', lineHeight: 1.8 }}>
          Des rituels sensuels qui enveloppent, hydratent et illuminent votre corps.
          Accordez-vous un moment de pur bien-être.
        </p>
      </section>

      {/* Routines */}
      {!loading && routines.length > 0 && (
        <section className="lunea-section">
          <div className="lunea-container">
            <p className="lunea-eyebrow" style={{ textAlign: 'center' }}>Nos programmes</p>
            <h2 className="lunea-heading" style={{ textAlign: 'center', marginBottom: '2.5rem' }}>Rituels guidés</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 20 }}>
              {routines.map(r => <RoutineCard key={r.id} routine={r} />)}
            </div>
          </div>
        </section>
      )}

      {/* Products */}
      <section className="lunea-section" style={{ paddingTop: routines.length ? '0' : undefined }}>
        <div className="lunea-container">
          <p className="lunea-eyebrow" style={{ textAlign: 'center' }}>Essentiels</p>
          <h2 className="lunea-heading" style={{ textAlign: 'center', marginBottom: '2.5rem' }}>Produits corps</h2>

          {loading ? (
            <p style={{ textAlign: 'center', color: 'var(--color-text-muted)', padding: '3rem' }}>Chargement...</p>
          ) : products.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem' }}>
              <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', marginBottom: '0.75rem' }}>Bientôt disponible</p>
              <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Notre collection corps arrive prochainement.</p>
            </div>
          ) : (
            <div className="lunea-product-grid">
              {products.map(p => (
                <div key={p.id} style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
                  <div style={{ aspectRatio: '1', background: 'var(--color-bg)', overflow: 'hidden' }}>
                    {p.image
                      ? <img src={p.image} alt={p.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      : <div style={{ width: '100%', height: '100%', background: 'var(--color-border)' }} />}
                  </div>
                  <div style={{ padding: '1rem' }}>
                    <p style={{ fontFamily: 'var(--font-heading)', fontSize: '0.95rem', marginBottom: 6 }}>{p.name}</p>
                    <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem', color: 'var(--color-primary)' }}>
                      {Number(p.price || 0).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
