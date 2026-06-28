import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useCart } from '../hooks/useCart'

function ProductCard({ product, i }) {
  const { addToCart } = useCart()
  const [adding, setAdding] = useState(false)

  const handleAdd = async (e) => {
    e.preventDefault()
    setAdding(true)
    await addToCart(product, 1)
    setTimeout(() => setAdding(false), 900)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ delay: i * 0.1, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="makeup-product-card"
    >
      <Link to={`/product/${product.slug}`} style={{ textDecoration: 'none', display: 'block' }}>
        {/* Image */}
        <div className="makeup-product-img-wrap">
          {product.main_image ? (
            <img src={product.main_image} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <div style={{
              width: '100%', height: '100%',
              background: `linear-gradient(135deg, ${['#e7d6bf','#dbc8a8','#c8ad8b','#b89870'][i % 4]} 0%, #8a6a4a 100%)`,
              display: 'flex', alignItems: 'flex-end', padding: 16,
            }}>
              <span style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.2em', color: 'rgba(255,255,255,0.5)' }}>
                SIÈCLE
              </span>
            </div>
          )}
          {product.badge && (
            <span className="makeup-product-badge">{product.badge}</span>
          )}
        </div>

        {/* Info */}
        <div style={{ padding: '16px 0 4px' }}>
          <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', color: '#c9a45c', marginBottom: 6 }}>
            {product.category_display || 'MAQUILLAGE'}
          </p>
          <h3 style={{
            fontSize: 14, fontWeight: 600, color: '#090807',
            margin: '0 0 6px', lineHeight: 1.4,
          }}>
            {product.name}
          </h3>
          <p style={{ fontSize: 13, color: '#86796e', margin: 0 }}>
            {product.price ? `${parseFloat(product.price).toFixed(2).replace('.', ',')} €` : '—'}
          </p>
        </div>
      </Link>

      <button
        onClick={handleAdd}
        className="makeup-product-add"
        disabled={adding}
      >
        {adding ? '✓ Ajouté' : 'Ajouter au panier'}
      </button>
    </motion.div>
  )
}

// Skeleton placeholder while loading
function SkeletonCard({ i }) {
  return (
    <div className="makeup-product-card" style={{ animation: 'makeupPulse 1.5s ease-in-out infinite' }}>
      <div style={{ paddingBottom: '130%', background: '#ede4d8', borderRadius: 2 }} />
      <div style={{ padding: '16px 0 4px' }}>
        <div style={{ height: 10, width: '40%', background: '#ede4d8', marginBottom: 10, borderRadius: 2 }} />
        <div style={{ height: 14, width: '75%', background: '#e8ddd0', marginBottom: 8, borderRadius: 2 }} />
        <div style={{ height: 12, width: '30%', background: '#ede4d8', borderRadius: 2 }} />
      </div>
    </div>
  )
}

export default function MakeupBestSellers() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/v1/siecle/products/?category=maquillage&ordering=-sold_count&limit=4')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        const list = data?.results ?? data ?? []
        setProducts(list.slice(0, 4))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <section style={{ background: '#f7f1e8', padding: '96px 0' }}>
      <div style={{ maxWidth: 1320, margin: '0 auto', padding: '0 24px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 52 }}
          className="makeup-section-header">
          <div>
            <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.22em', color: '#c9a45c', marginBottom: 12 }}>
              BEST-SELLERS
            </p>
            <h2 className="makeup-section-title" style={{ margin: 0 }}>
              Les favoris
            </h2>
          </div>
          <Link to="/boutique?categorie=maquillage" style={{
            fontSize: 12, fontWeight: 600, color: '#090807',
            letterSpacing: '0.08em', textDecoration: 'none',
            borderBottom: '1px solid #090807', paddingBottom: 2,
          }}>
            Voir tout →
          </Link>
        </div>

        {/* Grid */}
        <div className="makeup-products-grid">
          {loading
            ? [0, 1, 2, 3].map(i => <SkeletonCard key={i} i={i} />)
            : products.length > 0
              ? products.map((p, i) => <ProductCard key={p.id} product={p} i={i} />)
              : [0, 1, 2, 3].map(i => (
                  <div key={i} className="makeup-product-card">
                    <div style={{
                      paddingBottom: '130%',
                      background: `linear-gradient(135deg, ${['#e7d6bf','#dbc8a8','#c8ad8b','#b89870'][i]} 0%, #8a6a4a 100%)`,
                    }} />
                    <div style={{ padding: '16px 0 4px' }}>
                      <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', color: '#c9a45c', marginBottom: 6 }}>
                        {['FOND DE TEINT', 'ROUGE À LÈVRES', 'MASCARA', 'PALETTE'][i]}
                      </p>
                      <h3 style={{ fontSize: 14, fontWeight: 600, color: '#090807', margin: '0 0 6px' }}>
                        {['Lumière Velours', 'Rouge Intense', 'Volume Extrême', 'Palette Nuit Dorée'][i]}
                      </h3>
                      <p style={{ fontSize: 13, color: '#86796e', margin: 0 }}>
                        {['45,00 €', '38,00 €', '29,00 €', '89,00 €'][i]}
                      </p>
                    </div>
                  </div>
                ))
          }
        </div>
      </div>

      <style>{`
        .makeup-products-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 24px;
        }
        @media (max-width: 900px) {
          .makeup-products-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 480px) {
          .makeup-products-grid { grid-template-columns: 1fr; }
          .makeup-section-header { flex-direction: column; align-items: flex-start; gap: 16px; }
        }
        @keyframes makeupPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </section>
  )
}
