import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import MotionPage, { fadeUp } from '../components/MotionPage'
import Product3DViewer from '../components/Product3DViewer'
import ProductGrid from '../components/ProductGrid'
import Loader from '../components/Loader'
import { useCart } from '../hooks/useCart'
import { getProduct } from '../api/products'

const fmt = (p) => Number(p).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

export default function ProductDetail() {
  const { slug }                    = useParams()
  const navigate                    = useNavigate()
  const [product, setProduct]       = useState(null)
  const [loading, setLoading]       = useState(true)
  const [activeImg, setActiveImg]   = useState(0)
  const [size, setSize]             = useState('')
  const [show3d, setShow3d]         = useState(false)
  const [added, setAdded]           = useState(false)
  const { addItem, setIsOpen }      = useCart()

  useEffect(() => {
    setLoading(true)
    getProduct(slug)
      .then(setProduct)
      .catch(() => navigate('/shop'))
      .finally(() => setLoading(false))
  }, [slug, navigate])

  if (loading) return <Loader />
  if (!product) return null

  const rawGallery = product.gallery || []
  const images = rawGallery.length > 0
    ? rawGallery.map(url => ({ image: url }))
    : product.image ? [{ image: product.image }] : []
  const sizes   = product.sizes || []
  const related = product.related_products || []

  const handleAdd = () => {
    if (sizes.length > 0 && !size) return
    addItem(product, size || undefined)
    setAdded(true)
    setTimeout(() => setAdded(false), 2000)
    setTimeout(() => setIsOpen(true), 300)
  }

  return (
    <MotionPage style={{ paddingTop: 'var(--header-h)', minHeight: '100vh' }}>
      <div style={{ maxWidth: 1440, margin: '0 auto', padding: '40px 24px 80px' }}>

        {/* Breadcrumb */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 40, fontSize: 11, color: 'var(--siecle-muted)' }}>
          <Link to="/" style={{ color: 'var(--siecle-muted)' }}>Accueil</Link>
          <span>/</span>
          <Link to="/shop" style={{ color: 'var(--siecle-muted)' }}>Boutique</Link>
          {product.category && (
            <>
              <span>/</span>
              <Link to={`/shop?category=${product.category_slug || ''}`} style={{ color: 'var(--siecle-muted)' }}>
                {product.category}
              </Link>
            </>
          )}
          <span>/</span>
          <span style={{ color: 'var(--siecle-white)' }}>{product.name}</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 64, alignItems: 'start' }}
          className="siecle-product-layout">

          {/* Left: image/viewer */}
          <div>
            {/* Main image */}
            <div style={{ position: 'relative', aspectRatio: '3/4', background: 'var(--siecle-dark)', overflow: 'hidden', marginBottom: 12 }}>
              {show3d && product.model_3d_url ? (
                <Product3DViewer
                  modelUrl={product.model_3d_url}
                  fallbackImage={images[activeImg]?.image}
                  alt={product.name}
                />
              ) : images.length > 0 ? (
                <motion.img
                  key={activeImg}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  src={images[activeImg]?.image}
                  alt={product.name}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 48, color: 'rgba(241,237,229,0.1)', fontFamily: 'var(--font-heading)', fontWeight: 900 }}>
                    SIÈCLE
                  </span>
                </div>
              )}

              {/* 3D toggle */}
              {product.model_3d_url && (
                <button
                  onClick={() => setShow3d(v => !v)}
                  style={{
                    position: 'absolute', bottom: 12, right: 12,
                    padding: '8px 14px', background: 'rgba(9,9,9,0.7)',
                    border: '1px solid rgba(241,237,229,0.2)',
                    color: 'var(--siecle-white)', cursor: 'pointer', fontSize: 10,
                    fontWeight: 700, letterSpacing: '0.1em',
                  }}
                >
                  {show3d ? '📷 PHOTO' : '🔄 3D'}
                </button>
              )}
            </div>

            {/* Thumbnails */}
            {images.length > 1 && (
              <div style={{ display: 'flex', gap: 8, overflowX: 'auto' }}>
                {images.map((img, i) => (
                  <div key={i}
                    onClick={() => { setActiveImg(i); setShow3d(false) }}
                    style={{
                      width: 72, height: 90, flexShrink: 0, cursor: 'pointer',
                      overflow: 'hidden',
                      outline: activeImg === i ? '2px solid var(--siecle-beige)' : '2px solid transparent',
                      outlineOffset: 2,
                    }}
                  >
                    <img src={img.image} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right: info */}
          <div>
            {/* Category */}
            <motion.p variants={fadeUp} initial="hidden" animate="visible"
              style={{ color: 'var(--siecle-beige)', fontSize: 10, fontWeight: 800, letterSpacing: '0.16em', marginBottom: 8 }}
            >
              {product.category || 'SIÈCLE'}
            </motion.p>

            {/* Name */}
            <motion.h1 variants={fadeUp} initial="hidden" animate="visible" custom={1}
              style={{
                fontFamily: 'var(--font-heading)',
                fontSize: 'clamp(24px, 3.5vw, 38px)', fontWeight: 900,
                letterSpacing: '0.02em', color: 'var(--siecle-white)', marginBottom: 8, lineHeight: 1.1,
              }}
            >
              {product.name}
            </motion.h1>

            {/* Price */}
            <motion.p variants={fadeUp} initial="hidden" animate="visible" custom={2}
              style={{ fontSize: 22, fontWeight: 700, color: 'var(--siecle-beige)', marginBottom: 24 }}
            >
              {fmt(product.price)}
            </motion.p>

            {/* Description */}
            {product.description && (
              <motion.p variants={fadeUp} initial="hidden" animate="visible" custom={3}
                style={{ color: 'var(--siecle-muted)', fontSize: 14, lineHeight: 1.8, marginBottom: 28 }}
              >
                {product.description}
              </motion.p>
            )}

            {/* Size selector */}
            {sizes.length > 0 && (
              <motion.div variants={fadeUp} initial="hidden" animate="visible" custom={4}
                style={{ marginBottom: 24 }}
              >
                <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', color: 'rgba(241,237,229,0.6)', marginBottom: 12 }}>
                  TAILLE {size && `— ${size}`}
                </p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {sizes.map(s => (
                    <button
                      key={s}
                      onClick={() => setSize(s)}
                      style={{
                        width: 44, height: 44,
                        border: size === s ? '1px solid var(--siecle-beige)' : '1px solid rgba(241,237,229,0.2)',
                        background: size === s ? 'var(--siecle-beige)' : 'transparent',
                        color: size === s ? 'var(--siecle-black)' : 'var(--siecle-white)',
                        fontSize: 12, fontWeight: 700, cursor: 'pointer',
                        transition: 'all 0.15s',
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
                {sizes.length > 0 && !size && (
                  <p style={{ fontSize: 11, color: 'rgba(255,100,100,0.8)', marginTop: 8 }}>
                    Veuillez sélectionner une taille
                  </p>
                )}
              </motion.div>
            )}

            {/* Stock */}
            <motion.p variants={fadeUp} initial="hidden" animate="visible" custom={5}
              style={{ fontSize: 12, color: product.stock_quantity > 5 ? '#6FD08C' : product.stock_quantity > 0 ? 'var(--siecle-beige)' : '#FF6464', marginBottom: 24 }}
            >
              {product.stock_quantity > 10 ? 'En stock'
                : product.stock_quantity > 0 ? `Plus que ${product.stock_quantity} en stock`
                : 'Épuisé'}
            </motion.p>

            {/* CTA */}
            <motion.div variants={fadeUp} initial="hidden" animate="visible" custom={6}
              style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}
            >
              <button
                onClick={handleAdd}
                disabled={product.stock_quantity === 0}
                style={{
                  flex: 1, minWidth: 200, padding: '16px 24px',
                  background: added ? '#4CAF50' : product.stock_quantity === 0 ? 'var(--siecle-gray)' : 'var(--siecle-beige)',
                  color: added ? 'var(--siecle-white)' : 'var(--siecle-black)',
                  border: 'none', cursor: product.stock_quantity === 0 ? 'not-allowed' : 'pointer',
                  fontSize: 12, fontWeight: 800, letterSpacing: '0.14em',
                  transition: 'background 0.3s, color 0.3s',
                }}
              >
                {added ? '✓ AJOUTÉ' : product.stock_quantity === 0 ? 'ÉPUISÉ' : 'AJOUTER AU PANIER'}
              </button>
            </motion.div>

            {/* Meta */}
            {product.sku && (
              <motion.p variants={fadeUp} initial="hidden" animate="visible" custom={7}
                style={{ color: 'rgba(241,237,229,0.2)', fontSize: 11, marginTop: 24, letterSpacing: '0.08em' }}
              >
                REF: {product.sku}
              </motion.p>
            )}
          </div>
        </div>

        {/* Related products */}
        {related.length > 0 && (
          <section style={{ marginTop: 96 }}>
            <div style={{ textAlign: 'center', marginBottom: 48 }}>
              <p style={{ color: 'var(--siecle-beige)', fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', marginBottom: 8 }}>
                VOUS AIMEREZ AUSSI
              </p>
              <h2 style={{
                fontFamily: 'var(--font-heading)',
                fontSize: 28, fontWeight: 900, letterSpacing: '0.04em', color: 'var(--siecle-white)',
              }}>
                PRODUITS SIMILAIRES
              </h2>
            </div>
            <ProductGrid products={related.slice(0, 4)} columns={4} />
          </section>
        )}
      </div>

      <style>{`
        @media (max-width: 768px) {
          .siecle-product-layout { grid-template-columns: 1fr !important; gap: 32px !important; }
        }
      `}</style>
    </MotionPage>
  )
}
