import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'

function StepCard({ step, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.08 }}
      style={{
        display: 'flex', gap: 20, alignItems: 'flex-start',
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius)', padding: '1.25rem',
      }}
    >
      <div style={{
        flexShrink: 0, width: 36, height: 36, borderRadius: '50%',
        background: 'var(--color-primary)', color: 'white',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 14, fontWeight: 700,
      }}>
        {index + 1}
      </div>
      <div style={{ flex: 1 }}>
        <p style={{ fontFamily: 'var(--font-heading)', fontSize: '0.95rem', marginBottom: 4 }}>
          {step.title || step.product_name || `Étape ${index + 1}`}
        </p>
        {step.description && (
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
            {step.description}
          </p>
        )}
        {step.product && (
          <Link
            to={`/lunea/produit/${step.product.slug}/`}
            style={{ fontSize: 12, color: 'var(--color-primary)', marginTop: 8, display: 'inline-block' }}
          >
            Voir le produit →
          </Link>
        )}
      </div>
    </motion.div>
  )
}

function ProductCard({ product }) {
  const [adding, setAdding] = useState(false)

  async function handleAdd() {
    setAdding(true)
    try {
      await fetch('/api/v1/lunea/cart/add/', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: product.id, quantity: 1 }),
      })
    } catch { /* ignore */ }
    setTimeout(() => setAdding(false), 800)
  }

  return (
    <div style={{
      background: 'var(--color-surface)', border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius)', overflow: 'hidden',
    }}>
      <div style={{ aspectRatio: '1', overflow: 'hidden' }}>
        {product.image
          ? <img src={product.image} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          : <div style={{ width: '100%', height: '100%', background: 'var(--color-border)' }} />}
      </div>
      <div style={{ padding: '1rem' }}>
        <p style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: 6 }}>{product.name}</p>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-heading)', fontSize: '0.95rem', color: 'var(--color-primary)' }}>
            {Number(product.price || 0).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
          </span>
          <button onClick={handleAdd} className="btn-primary" style={{ padding: '5px 12px', fontSize: 11 }}>
            {adding ? '✓' : '+ Panier'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function LuneaRituelDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [routine, setRoutine] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    fetch(`/api/v1/lunea/routines/${slug}/`, { credentials: 'include' })
      .then(r => {
        if (r.status === 404) { setNotFound(true); return null }
        return r.ok ? r.json() : null
      })
      .then(d => { if (d) setRoutine(d) })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [slug])

  useEffect(() => {
    if (routine) document.title = `${routine.name} — LUNEA`
  }, [routine])

  if (loading) {
    return (
      <div style={{ paddingTop: 'calc(var(--header-h) + 4rem)', textAlign: 'center', color: 'var(--color-text-muted)', minHeight: '60vh' }}>
        Chargement...
      </div>
    )
  }

  if (notFound || !routine) {
    return (
      <div style={{ paddingTop: 'calc(var(--header-h) + 4rem)', textAlign: 'center', minHeight: '60vh' }}>
        <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.4rem', marginBottom: '1rem' }}>Rituel introuvable</p>
        <button onClick={() => navigate('/lunea/rituels/')} className="btn-outline">
          Retour aux rituels
        </button>
      </div>
    )
  }

  const steps = routine.steps ?? []
  const products = routine.products ?? []

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      {/* Hero */}
      <section style={{
        padding: '4rem 24px',
        background: 'linear-gradient(160deg, var(--color-bg) 0%, var(--color-surface) 100%)',
        position: 'relative', overflow: 'hidden',
      }}>
        <div style={{
          position: 'absolute', top: '-10%', right: '0%',
          width: 500, height: 500, borderRadius: '50%',
          background: 'radial-gradient(circle, var(--color-primary) 0%, transparent 70%)',
          opacity: 0.07, pointerEvents: 'none',
        }} />
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
          <Link to="/lunea/rituels/" style={{ fontSize: 13, color: 'var(--color-text-muted)', display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: '1.5rem', textDecoration: 'none' }}>
            ← Rituels
          </Link>
          {routine.steps_count && (
            <p className="lunea-eyebrow">{routine.steps_count} étapes</p>
          )}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="lunea-heading"
          >
            {routine.name}
          </motion.h1>
          {routine.description && (
            <p style={{ fontSize: 15, color: 'var(--color-text-muted)', maxWidth: 600, lineHeight: 1.8, marginTop: '1rem' }}>
              {routine.description}
            </p>
          )}
          {routine.total_price && (
            <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', marginTop: '1.5rem', color: 'var(--color-primary)' }}>
              Pack complet : {Number(routine.total_price).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
            </p>
          )}
        </div>
      </section>

      {/* Hero image */}
      {routine.image && (
        <div style={{ maxWidth: 900, margin: '0 auto', padding: '0 24px' }}>
          <img
            src={routine.image}
            alt={routine.name}
            style={{ width: '100%', borderRadius: 'var(--radius)', maxHeight: 420, objectFit: 'cover' }}
          />
        </div>
      )}

      <div style={{ maxWidth: 900, margin: '0 auto', padding: '3rem 24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: steps.length > 0 && products.length > 0 ? '1fr 1fr' : '1fr', gap: 40 }}>
          {/* Steps */}
          {steps.length > 0 && (
            <div>
              <p className="lunea-eyebrow">Le protocole</p>
              <h2 className="lunea-heading" style={{ fontSize: '1.5rem', marginBottom: '1.5rem' }}>Étapes du rituel</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {steps.map((step, i) => <StepCard key={step.id ?? i} step={step} index={i} />)}
              </div>
            </div>
          )}

          {/* Products in this ritual */}
          {products.length > 0 && (
            <div>
              <p className="lunea-eyebrow">La sélection</p>
              <h2 className="lunea-heading" style={{ fontSize: '1.5rem', marginBottom: '1.5rem' }}>Produits inclus</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
                {products.map(p => <ProductCard key={p.id} product={p} />)}
              </div>
            </div>
          )}
        </div>

        {/* CTA — add all to cart */}
        {products.length > 0 && (
          <div style={{
            marginTop: '3rem', padding: '2rem', textAlign: 'center',
            background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)',
          }}>
            <p className="lunea-eyebrow">Le pack complet</p>
            <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', marginBottom: '1rem' }}>
              Adoptez le rituel en entier
            </p>
            <button
              className="btn-primary"
              style={{ padding: '12px 32px', fontSize: 14 }}
              onClick={async () => {
                await Promise.all(products.map(p =>
                  fetch('/api/v1/lunea/cart/add/', {
                    method: 'POST', credentials: 'include',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_id: p.id, quantity: 1 }),
                  })
                ))
                navigate('/lunea/panier/')
              }}
            >
              Ajouter le pack au panier
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
