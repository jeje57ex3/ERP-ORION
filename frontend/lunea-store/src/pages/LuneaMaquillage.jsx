import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const FILTERS = [
  { key: '', label: 'Tous' },
  { key: 'levres', label: 'Lèvres' },
  { key: 'yeux', label: 'Yeux' },
  { key: 'teint', label: 'Teint' },
  { key: 'ongles', label: 'Ongles' },
  { key: 'sourcils', label: 'Sourcils' },
]

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
    <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', overflow: 'hidden' }}>
      <Link to={`/lunea/produit/${product.slug}/`} style={{ textDecoration: 'none', color: 'inherit', display: 'block' }}>
        <div style={{ aspectRatio: '1', background: 'var(--color-bg)', overflow: 'hidden', position: 'relative' }}>
          {product.image
            ? <img src={product.image} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            : <div style={{ width: '100%', height: '100%', background: 'var(--color-border)' }} />}
          {product.shade_count > 1 && (
            <span style={{
              position: 'absolute', bottom: 8, right: 8, fontSize: 10,
              background: 'rgba(0,0,0,0.6)', color: 'white',
              padding: '2px 8px', borderRadius: 10,
            }}>{product.shade_count} teintes</span>
          )}
        </div>
        <div style={{ padding: '1rem 1rem 0' }}>
          <p style={{ fontSize: 11, color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>
            {product.sub_category || 'Maquillage'}
          </p>
          <p style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', marginBottom: 8 }}>{product.name}</p>
        </div>
      </Link>
      <div style={{ padding: '0 1rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontFamily: 'var(--font-heading)', fontSize: '0.95rem' }}>
          {Number(product.price || 0).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
        </span>
        <button onClick={handleAdd} className="btn-primary" style={{ padding: '5px 14px', fontSize: 11 }}>
          {adding ? '✓' : '+ Panier'}
        </button>
      </div>
    </div>
  )
}

export default function LuneaMaquillage() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeFilter, setActiveFilter] = useState('')

  useEffect(() => {
    document.title = 'Maquillage — LUNEA'
  }, [])

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams({ category: 'maquillage' })
    if (activeFilter) params.set('sub_category', activeFilter)
    fetch(`/api/v1/lunea/products/?${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setProducts(d?.results ?? d ?? []))
      .catch(() => setProducts([]))
      .finally(() => setLoading(false))
  }, [activeFilter])

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      {/* Hero */}
      <section style={{
        padding: '5rem 24px', textAlign: 'center',
        background: 'linear-gradient(160deg, var(--color-bg) 0%, #f8e8e880 100%)',
      }}>
        <p className="lunea-eyebrow">Couleur & Expression</p>
        <h1 className="lunea-heading">Maquillage</h1>
        <p style={{ fontSize: 15, color: 'var(--color-text-muted)', maxWidth: 520, margin: '1rem auto 0', lineHeight: 1.8 }}>
          Des teintes pensées pour toutes les carnations, des formules longue tenue
          qui subliment sans masquer votre beauté naturelle.
        </p>
      </section>

      <section className="lunea-section">
        <div className="lunea-container">
          {/* Filters */}
          <div style={{ display: 'flex', gap: 8, marginBottom: '2rem', flexWrap: 'wrap' }}>
            {FILTERS.map(f => (
              <button
                key={f.key}
                onClick={() => setActiveFilter(f.key)}
                style={{
                  padding: '6px 18px', borderRadius: 20, fontSize: 13, cursor: 'pointer',
                  background: activeFilter === f.key ? 'var(--color-primary)' : 'var(--color-surface)',
                  color: activeFilter === f.key ? 'white' : 'var(--color-text)',
                  border: `1px solid ${activeFilter === f.key ? 'var(--color-primary)' : 'var(--color-border)'}`,
                  transition: 'all 0.2s',
                }}
              >{f.label}</button>
            ))}
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--color-text-muted)' }}>Chargement...</div>
          ) : products.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '4rem' }}>
              <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', marginBottom: '0.75rem' }}>Bientôt disponible</p>
              <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>Notre collection maquillage arrive prochainement.</p>
            </div>
          ) : (
            <div className="lunea-product-grid">
              {products.map(p => <ProductCard key={p.id} product={p} />)}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
