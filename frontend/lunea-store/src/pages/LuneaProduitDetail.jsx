import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'

const CATEGORY_LABELS = {
  soins: 'Soins visage',
  maquillage: 'Maquillage',
  rituels: 'Rituels corps',
}

const CATEGORY_ROUTES = {
  soins: '/lunea/soins/',
  maquillage: '/lunea/maquillage/',
  rituels: '/lunea/rituels/',
}

export default function LuneaProduitDetail() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [qty, setQty] = useState(1)
  const [adding, setAdding] = useState(false)
  const [added, setAdded] = useState(false)
  const [selectedImage, setSelectedImage] = useState(0)

  useEffect(() => {
    fetch(`/api/v1/lunea/products/${slug}/`, { credentials: 'include' })
      .then(r => {
        if (r.status === 404) { setNotFound(true); return null }
        return r.ok ? r.json() : null
      })
      .then(d => { if (d) setProduct(d) })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [slug])

  useEffect(() => {
    if (product) document.title = `${product.name} — LUNEA`
  }, [product])

  async function handleAddToCart() {
    setAdding(true)
    try {
      const r = await fetch('/api/v1/lunea/cart/add/', {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: product.id, quantity: qty }),
      })
      if (r.ok) { setAdded(true); setTimeout(() => setAdded(false), 2500) }
    } catch { /* ignore */ }
    setAdding(false)
  }

  if (loading) {
    return (
      <div style={{ paddingTop: 'calc(var(--header-h) + 4rem)', textAlign: 'center', color: 'var(--color-text-muted)', minHeight: '60vh' }}>
        Chargement...
      </div>
    )
  }

  if (notFound || !product) {
    return (
      <div style={{ paddingTop: 'calc(var(--header-h) + 4rem)', textAlign: 'center', minHeight: '60vh' }}>
        <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.4rem', marginBottom: '1rem' }}>Produit introuvable</p>
        <button onClick={() => navigate('/lunea/boutique/')} className="btn-outline">
          Retour à la boutique
        </button>
      </div>
    )
  }

  const images = product.images?.length ? product.images : (product.image ? [{ url: product.image }] : [])
  const categoryLabel = CATEGORY_LABELS[product.category] ?? 'Boutique'
  const categoryRoute = CATEGORY_ROUTES[product.category] ?? '/lunea/boutique/'

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '2.5rem 24px' }}>
        {/* Breadcrumb */}
        <nav style={{ display: 'flex', gap: 8, fontSize: 13, color: 'var(--color-text-muted)', marginBottom: '2rem', flexWrap: 'wrap' }}>
          <Link to="/lunea/" style={{ color: 'var(--color-text-muted)', textDecoration: 'none' }}>LUNEA</Link>
          <span>/</span>
          <Link to={categoryRoute} style={{ color: 'var(--color-text-muted)', textDecoration: 'none' }}>{categoryLabel}</Link>
          <span>/</span>
          <span style={{ color: 'var(--color-text)' }}>{product.name}</span>
        </nav>

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: 56, alignItems: 'start' }}>
          {/* Images */}
          <div>
            {/* Main image */}
            <motion.div
              key={selectedImage}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
              style={{
                aspectRatio: '1', borderRadius: 'var(--radius)', overflow: 'hidden',
                background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                marginBottom: 12,
              }}
            >
              {images[selectedImage]
                ? <img src={images[selectedImage].url ?? images[selectedImage]} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                : <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-text-muted)', fontSize: 13 }}>
                    Aucune image
                  </div>
              }
            </motion.div>
            {/* Thumbnails */}
            {images.length > 1 && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {images.map((img, i) => (
                  <button
                    key={i}
                    onClick={() => setSelectedImage(i)}
                    style={{
                      width: 64, height: 64, borderRadius: 8, overflow: 'hidden', cursor: 'pointer',
                      border: `2px solid ${i === selectedImage ? 'var(--color-primary)' : 'var(--color-border)'}`,
                      padding: 0, background: 'none',
                    }}
                  >
                    <img src={img.url ?? img} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Info */}
          <div>
            {product.sub_category && (
              <p className="lunea-eyebrow">{product.sub_category}</p>
            )}
            <h1 className="lunea-heading" style={{ fontSize: 'clamp(1.4rem, 3vw, 2rem)', marginBottom: '0.75rem' }}>
              {product.name}
            </h1>

            {product.short_description && (
              <p style={{ fontSize: 15, color: 'var(--color-text-muted)', lineHeight: 1.7, marginBottom: '1.5rem' }}>
                {product.short_description}
              </p>
            )}

            {/* Price */}
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: '1.75rem' }}>
              <span style={{ fontFamily: 'var(--font-heading)', fontSize: '1.6rem', color: 'var(--color-primary)' }}>
                {Number(product.price || 0).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
              </span>
              {product.compare_price && Number(product.compare_price) > Number(product.price) && (
                <span style={{ fontSize: '1rem', color: 'var(--color-text-muted)', textDecoration: 'line-through' }}>
                  {Number(product.compare_price).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
                </span>
              )}
            </div>

            {/* Shade selector */}
            {product.shades?.length > 0 && (
              <div style={{ marginBottom: '1.5rem' }}>
                <p style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 10 }}>
                  Teinte
                </p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {product.shades.map(shade => (
                    <button
                      key={shade.id}
                      title={shade.name}
                      style={{
                        width: 28, height: 28, borderRadius: '50%', cursor: 'pointer',
                        background: shade.hex_color ?? '#ccc',
                        border: '2px solid var(--color-border)',
                      }}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Quantity */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: '1.5rem' }}>
              <p style={{ fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Quantité</p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  onClick={() => setQty(q => Math.max(1, q - 1))}
                  style={{
                    width: 32, height: 32, borderRadius: 6, border: '1px solid var(--color-border)',
                    background: 'var(--color-surface)', cursor: 'pointer', fontSize: 16,
                  }}
                >−</button>
                <span style={{ minWidth: 24, textAlign: 'center', fontWeight: 600 }}>{qty}</span>
                <button
                  onClick={() => setQty(q => q + 1)}
                  style={{
                    width: 32, height: 32, borderRadius: 6, border: '1px solid var(--color-border)',
                    background: 'var(--color-surface)', cursor: 'pointer', fontSize: 16,
                  }}
                >+</button>
              </div>
            </div>

            {/* Add to cart */}
            <button
              onClick={handleAddToCart}
              disabled={adding}
              className="btn-primary"
              style={{ width: '100%', padding: '14px', fontSize: 15, marginBottom: 12 }}
            >
              {added ? 'Ajouté au panier ✓' : adding ? 'Ajout...' : 'Ajouter au panier'}
            </button>

            <Link
              to="/lunea/panier/"
              style={{ display: 'block', textAlign: 'center', fontSize: 13, color: 'var(--color-text-muted)', textDecoration: 'none', padding: '8px 0' }}
            >
              Voir le panier
            </Link>

            {/* Stock / availability */}
            {product.stock !== undefined && (
              <p style={{ fontSize: 12, color: product.stock > 0 ? '#3a8c5c' : '#c0392b', marginTop: 12 }}>
                {product.stock > 0 ? `En stock — ${product.stock} disponible${product.stock > 1 ? 's' : ''}` : 'Rupture de stock'}
              </p>
            )}

            {/* Description */}
            {product.description && (
              <div style={{ marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid var(--color-border)' }}>
                <p style={{ fontSize: 13, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.75rem' }}>
                  Description
                </p>
                <p style={{ fontSize: 14, color: 'var(--color-text-muted)', lineHeight: 1.8, whiteSpace: 'pre-line' }}>
                  {product.description}
                </p>
              </div>
            )}

            {/* Ingredients */}
            {product.ingredients && (
              <div style={{ marginTop: '1.5rem' }}>
                <p style={{ fontSize: 13, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.5rem' }}>
                  Ingrédients
                </p>
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', lineHeight: 1.7 }}>
                  {product.ingredients}
                </p>
              </div>
            )}

            {/* How to use */}
            {product.how_to_use && (
              <div style={{ marginTop: '1.5rem' }}>
                <p style={{ fontSize: 13, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.5rem' }}>
                  Comment l'utiliser
                </p>
                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', lineHeight: 1.7 }}>
                  {product.how_to_use}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
