import { useState, useEffect } from 'react'
import { useLocation, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import MakeupLayout from '../layouts/MakeupLayout'
import { useCart } from '../hooks/useCart'
import { makeupBestSellers } from '../data/makeupProducts'

const TYPE_LABELS = {
  teint:       'Teint',
  levres:      'Lèvres',
  yeux:        'Yeux',
  accessoires: 'Accessoires',
}
const FILTER_LABELS = {
  new:          'Nouveautés',
  'best-sellers': 'Best-sellers',
}

const FILTERS = [
  { label: 'Tout',         href: '/maquillage/shop' },
  { label: 'Nouveautés',   href: '/maquillage/shop?filter=new' },
  { label: 'Best-sellers', href: '/maquillage/shop?filter=best-sellers' },
  { label: 'Teint',        href: '/maquillage/shop?type=teint' },
  { label: 'Lèvres',       href: '/maquillage/shop?type=levres' },
  { label: 'Yeux',         href: '/maquillage/shop?type=yeux' },
  { label: 'Accessoires',  href: '/maquillage/shop?type=accessoires' },
]

function ProductCard({ product }) {
  const { addToCart } = useCart()
  const [added, setAdded] = useState(false)

  const handleAdd = () => {
    addToCart({ id: product.id, name: product.name, price: product.priceRaw ?? product.price ?? 0 })
    setAdded(true)
    setTimeout(() => setAdded(false), 1600)
  }

  return (
    <motion.article
      className="makeup-product-card"
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
      viewport={{ once: true }}
    >
      <div className="makeup-product-img-wrap">
        <div className="makeup-product-img-inner" style={{ background: 'var(--beauty-beige)' }}>
          <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
            <ellipse cx="32" cy="32" rx="20" ry="28" fill="var(--beauty-beige-dark)" opacity="0.5" />
            <ellipse cx="32" cy="32" rx="12" ry="18" fill="var(--beauty-gold)" opacity="0.4" />
          </svg>
        </div>
      </div>
      <p className="makeup-product-name">{product.name}</p>
      <p className="makeup-product-subtitle">{product.subtitle}</p>
      <p className="makeup-product-price">{product.price}</p>
      <button className="makeup-product-add-btn" onClick={handleAdd} disabled={added}>
        {added ? 'Ajouté ✓' : 'Ajouter au panier'}
      </button>
    </motion.article>
  )
}

export default function MakeupShop() {
  const location = useLocation()
  const params   = new URLSearchParams(location.search)
  const type     = params.get('type')
  const filter   = params.get('filter')

  const [products, setProducts] = useState(null)

  const pageTitle = type
    ? TYPE_LABELS[type] ?? type
    : filter
    ? FILTER_LABELS[filter] ?? filter
    : 'Boutique'

  useEffect(() => {
    document.title = `SIÈCLE Beauty — ${pageTitle}`
    const q = type
      ? `category=maquillage&type=${type}`
      : filter === 'best-sellers'
      ? 'category=maquillage&best_seller=true'
      : filter === 'new'
      ? 'category=maquillage&ordering=-created_at'
      : 'category=maquillage'

    fetch(`/api/v1/siecle/products/?${q}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        const list = data?.products ?? data?.results ?? null
        if (list && list.length > 0) {
          setProducts(list.map(p => ({
            id:       p.id,
            name:     p.name,
            subtitle: p.short_description || '',
            price:    `${parseFloat(p.price).toFixed(2).replace('.', ',')} €`,
            priceRaw: parseFloat(p.price),
          })))
        } else {
          setProducts(makeupBestSellers)
        }
      })
      .catch(() => setProducts(makeupBestSellers))
  }, [location.search])

  return (
    <MakeupLayout>
      {/* Shop banner */}
      <section style={{ background: 'var(--beauty-white)', borderBottom: '1px solid var(--beauty-border)', padding: '40px 0' }}>
        <div className="beauty-container">
          <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.2em', color: 'var(--beauty-gold)', marginBottom: 10, textTransform: 'uppercase' }}>
            SIÈCLE BEAUTY
          </p>
          <h1 style={{
            fontFamily: 'var(--beauty-serif)',
            fontSize: 'clamp(2rem, 5vw, 3.5rem)',
            fontWeight: 400,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--beauty-black)',
          }}>
            {pageTitle}
          </h1>
        </div>
      </section>

      {/* Filters */}
      <section style={{ background: 'var(--beauty-white)', borderBottom: '1px solid var(--beauty-border)', padding: '16px 0', position: 'sticky', top: 72, zIndex: 40 }}>
        <div className="beauty-container">
          <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 2 }}>
            {FILTERS.map(f => {
              const isActive = f.href === `/maquillage/shop${location.search}`
                || (f.href === '/maquillage/shop' && !location.search)
              return (
                <Link
                  key={f.href}
                  to={f.href}
                  style={{
                    padding: '8px 18px',
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: '0.12em',
                    textTransform: 'uppercase',
                    whiteSpace: 'nowrap',
                    border: '1.5px solid',
                    borderColor: isActive ? 'var(--beauty-black)' : 'var(--beauty-border)',
                    background: isActive ? 'var(--beauty-black)' : 'transparent',
                    color: isActive ? 'var(--beauty-white)' : 'var(--beauty-muted)',
                    transition: 'all 0.2s',
                  }}
                >
                  {f.label}
                </Link>
              )
            })}
          </div>
        </div>
      </section>

      {/* Product grid */}
      <section style={{ padding: '64px 0 96px' }}>
        <div className="beauty-container">
          {!products ? (
            <div className="makeup-products-grid">
              {[1,2,3,4].map(i => (
                <div key={i} className="makeup-product-card makeup-product-skeleton">
                  <div className="makeup-product-img-wrap" />
                  <div className="makeup-product-skeleton-line" style={{ width: '70%' }} />
                  <div className="makeup-product-skeleton-line" style={{ width: '50%' }} />
                </div>
              ))}
            </div>
          ) : products.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '80px 0', color: 'var(--beauty-muted)' }}>
              <p style={{ fontSize: 14 }}>Aucun produit disponible dans cette catégorie.</p>
              <Link to="/maquillage/shop" style={{ marginTop: 20, display: 'inline-block', fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: 'var(--beauty-gold)' }}>
                VOIR TOUS LES PRODUITS →
              </Link>
            </div>
          ) : (
            <div className="makeup-products-grid">
              {products.map(p => <ProductCard key={p.id} product={p} />)}
            </div>
          )}
        </div>
      </section>
    </MakeupLayout>
  )
}
