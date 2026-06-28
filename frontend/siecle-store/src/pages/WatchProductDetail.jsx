import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import Watch3DCustomizer from '../components/Watch3DCustomizer'
import ProductGrid from '../components/ProductGrid'
import Loader from '../components/Loader'
import MotionPage, { fadeUp } from '../components/MotionPage'
import { useCart } from '../hooks/useCart'
import { getProduct } from '../api/products'

const fmt = (p) => Number(p).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

const FEATURES = [
  { icon: '◎', label: 'Mouvement automatique', sub: 'Mécanisme de précision' },
  { icon: '⬡', label: 'Verre saphir', sub: 'Anti-rayures, anti-reflets' },
  { icon: '◈', label: 'Boîtier acier 316L', sub: 'Résistance et légèreté' },
  { icon: '⌒', label: 'Étanchéité 5 ATM', sub: 'Résiste aux éclaboussures' },
]

export default function WatchProductDetail() {
  const { slug }          = useParams()
  const navigate          = useNavigate()
  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    document.title = 'Montre SIÈCLE — Personnalisation 3D'
    setLoading(true)
    getProduct(slug)
      .then(data => { setProduct(data); if (data?.name) document.title = `${data.name} — SIÈCLE` })
      .catch(() => navigate('/montres'))
      .finally(() => setLoading(false))
    return () => { document.title = 'SIÈCLE' }
  }, [slug, navigate])

  if (loading) return <Loader />
  if (!product) return null

  const isCustomizable = product.is_customizable
  const related = product.related_products || []

  return (
    <MotionPage style={{ paddingTop: 'var(--header-h)', background: '#000', minHeight: '100vh' }}>
      {/* Breadcrumb */}
      <div style={{
        maxWidth: 1440, margin: '0 auto', padding: '24px 24px 0',
        display: 'flex', gap: 8, alignItems: 'center',
        fontSize: 11, color: 'rgba(255,255,255,0.35)',
      }}>
        <Link to="/" style={{ color: 'inherit' }}>Accueil</Link>
        <span>/</span>
        <Link to="/montres" style={{ color: 'inherit' }}>Montres</Link>
        <span>/</span>
        <span style={{ color: 'rgba(255,255,255,0.7)' }}>{product.name}</span>
      </div>

      {/* ── Configurateur 3D (si personnalisable) ── */}
      {isCustomizable ? (
        <Watch3DCustomizer
          product={product}
          basePrice={product.price}
          modelUrl={product.model_3d_url || null}
          fallbackImage={product.image || null}
        />
      ) : (
        /* ── Page produit standard pour montres non-configurables ── */
        <div style={{ maxWidth: 1440, margin: '0 auto', padding: '40px 24px 80px' }}>
          <div
            style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 64, alignItems: 'start' }}
            className="siecle-product-layout"
          >
            {/* Image */}
            <div style={{ aspectRatio: '3/4', background: '#111', overflow: 'hidden' }}>
              {product.image ? (
                <img src={product.image} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              ) : (
                <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 72, fontWeight: 900, color: 'rgba(255,255,255,0.04)' }}>
                    SIÈCLE
                  </span>
                </div>
              )}
            </div>

            {/* Info */}
            <div>
              <motion.p variants={fadeUp} initial="hidden" animate="visible"
                style={{ color: '#D8C7A3', fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', marginBottom: 8 }}>
                MONTRES SIÈCLE
              </motion.p>
              <motion.h1 variants={fadeUp} initial="hidden" animate="visible" custom={1}
                style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(22px,3vw,36px)', fontWeight: 900, color: '#fff', marginBottom: 8 }}>
                {product.name}
              </motion.h1>
              <motion.p variants={fadeUp} initial="hidden" animate="visible" custom={2}
                style={{ fontSize: 22, color: '#D8C7A3', fontWeight: 700, marginBottom: 24 }}>
                {fmt(product.price)}
              </motion.p>
              {product.description && (
                <motion.p variants={fadeUp} initial="hidden" animate="visible" custom={3}
                  style={{ fontSize: 14, lineHeight: 1.8, color: 'rgba(255,255,255,0.5)', marginBottom: 28 }}>
                  {product.description}
                </motion.p>
              )}
              <Link to={`/product/${slug}`}
                style={{
                  display: 'inline-block', padding: '16px 32px',
                  background: '#D8C7A3', color: '#000',
                  fontSize: 11, fontWeight: 800, letterSpacing: '0.14em',
                  textDecoration: 'none',
                }}>
                VOIR LE PRODUIT COMPLET
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* ── Features band ── */}
      <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{
          maxWidth: 1440, margin: '0 auto', padding: '0 24px',
          display: 'grid', gridTemplateColumns: 'repeat(4,1fr)',
        }} className="watch-features-grid">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.label}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              style={{
                padding: '28px 20px',
                borderRight: i < 3 ? '1px solid rgba(255,255,255,0.06)' : 'none',
                display: 'flex', alignItems: 'center', gap: 14,
              }}
            >
              <span style={{ fontSize: 22, color: '#D8C7A3', flexShrink: 0 }}>{f.icon}</span>
              <div>
                <p style={{ fontSize: 12, fontWeight: 700, color: '#fff', margin: '0 0 3px' }}>{f.label}</p>
                <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', margin: 0 }}>{f.sub}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ── Product description (below configurator) ── */}
      {product.description && isCustomizable && (
        <div style={{ maxWidth: 800, margin: '72px auto', padding: '0 24px', textAlign: 'center' }}>
          <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.24em', color: '#D8C7A3', marginBottom: 16 }}>
            À PROPOS
          </p>
          <p style={{ fontSize: 15, lineHeight: 1.9, color: 'rgba(255,255,255,0.45)' }}>
            {product.description}
          </p>
        </div>
      )}

      {/* ── Livraison / retours ── */}
      <div style={{
        maxWidth: 1440, margin: '0 auto', padding: '0 24px 80px',
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 24,
      }} className="watch-info-grid">
        {[
          { title: 'Livraison offerte', text: 'Expédition sous 3 jours ouvrés. Livraison offerte dès 50 €.' },
          { title: 'Retours 14 jours', text: 'Retour gratuit sous 14 jours. Remboursement intégral garanti.' },
          { title: 'Paiement sécurisé', text: 'Paiement via Stripe. Vos données bancaires sont protégées.' },
        ].map(item => (
          <motion.div
            key={item.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            style={{
              padding: '28px', border: '1px solid rgba(255,255,255,0.07)',
              background: 'rgba(255,255,255,0.02)',
            }}
          >
            <h3 style={{ fontSize: 13, fontWeight: 800, color: '#D8C7A3', letterSpacing: '0.08em', marginBottom: 10 }}>
              {item.title}
            </h3>
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)', lineHeight: 1.7, margin: 0 }}>
              {item.text}
            </p>
          </motion.div>
        ))}
      </div>

      {/* ── Related products ── */}
      {related.length > 0 && (
        <section style={{ maxWidth: 1440, margin: '0 auto', padding: '0 24px 96px' }}>
          <div style={{ textAlign: 'center', marginBottom: 48 }}>
            <p style={{ color: '#D8C7A3', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 10 }}>
              VOUS AIMEREZ AUSSI
            </p>
            <h2 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 28, fontWeight: 900, color: '#fff', letterSpacing: '0.04em' }}>
              MONTRES SIMILAIRES
            </h2>
          </div>
          <ProductGrid products={related.slice(0, 4)} columns={4} />
        </section>
      )}

      <style>{`
        @media (max-width: 768px) {
          .siecle-product-layout { grid-template-columns: 1fr !important; }
          .watch-features-grid   { grid-template-columns: 1fr 1fr !important; }
          .watch-info-grid       { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </MotionPage>
  )
}
