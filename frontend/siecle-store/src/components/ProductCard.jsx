import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useCart } from '../hooks/useCart'

export default function ProductCard({ product, index = 0 }) {
  const [hovered, setHovered] = useState(false)
  const { addItem }           = useCart()

  const img  = product.image || product.gallery?.[0] || null
  const img2 = product.gallery?.[1] || null

  const fmtPrice = (p) =>
    Number(p).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

  return (
    <motion.article
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ delay: index * 0.06, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ position: 'relative' }}
    >
      {/* Image wrapper */}
      <div style={{
        position: 'relative', overflow: 'hidden',
        aspectRatio: '3/4', background: '#111',
        marginBottom: 16,
      }}>
        {img ? (
          <>
            <img src={img} alt={product.name}
              style={{
                width: '100%', height: '100%', objectFit: 'cover',
                transition: 'transform 0.6s ease, opacity 0.3s ease',
                transform: hovered ? 'scale(1.04)' : 'scale(1)',
                opacity: hovered && img2 ? 0 : 1,
                position: 'absolute', inset: 0,
              }}
            />
            {img2 && (
              <img src={img2} alt=""
                style={{
                  width: '100%', height: '100%', objectFit: 'cover',
                  transition: 'opacity 0.4s ease',
                  opacity: hovered ? 1 : 0,
                  position: 'absolute', inset: 0,
                }}
              />
            )}
          </>
        ) : (
          <div style={{
            width: '100%', height: '100%', display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            color: 'rgba(255,255,255,0.15)', fontSize: 12, letterSpacing: '0.1em',
          }}>
            SIÈCLE
          </div>
        )}

        {/* Badges */}
        <div style={{ position: 'absolute', top: 12, left: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {product.is_popular && (
            <span style={{
              background: 'var(--siecle-beige)', color: '#000',
              fontSize: 9, fontWeight: 800, letterSpacing: '0.12em',
              padding: '3px 8px',
            }}>POPULAIRE</span>
          )}
          {product.is_new && (
            <span style={{
              background: '#fff', color: '#000',
              fontSize: 9, fontWeight: 800, letterSpacing: '0.12em',
              padding: '3px 8px',
            }}>NOUVEAU</span>
          )}
          {product.stock_quantity === 0 && (
            <span style={{
              background: 'rgba(0,0,0,0.7)', color: 'rgba(255,255,255,0.5)',
              fontSize: 9, fontWeight: 800, letterSpacing: '0.12em',
              padding: '3px 8px',
            }}>ÉPUISÉ</span>
          )}
        </div>

        {/* Quick add */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: hovered ? 1 : 0 }}
          transition={{ duration: 0.2 }}
          style={{
            position: 'absolute', bottom: 12, left: 12, right: 12,
          }}
        >
          {product.stock_quantity > 0 && (!product.sizes || product.sizes.length === 0) ? (
            <button
              onClick={(e) => { e.preventDefault(); addItem(product) }}
              style={{
                width: '100%', padding: '10px 0',
                background: '#fff', color: '#000',
                fontSize: 11, fontWeight: 800, letterSpacing: '0.12em',
                border: 'none', cursor: 'pointer',
              }}
            >
              AJOUTER AU PANIER
            </button>
          ) : (
            <Link to={`/product/${product.slug}`} style={{
              display: 'block', width: '100%', padding: '10px 0',
              background: '#fff', color: '#000', textAlign: 'center',
              fontSize: 11, fontWeight: 800, letterSpacing: '0.12em',
            }}>
              {product.sizes?.length > 0 ? 'CHOISIR LA TAILLE' : 'VOIR LE PRODUIT'}
            </Link>
          )}
        </motion.div>
      </div>

      {/* Info */}
      <Link to={`/product/${product.slug}`} style={{ display: 'block' }}>
        <p style={{ color: 'var(--siecle-muted)', fontSize: 10, letterSpacing: '0.12em', marginBottom: 4 }}>
          {product.category || ''}
        </p>
        <p style={{ color: '#fff', fontSize: 14, fontWeight: 500, marginBottom: 4, lineHeight: 1.3 }}>
          {product.name}
        </p>
        <p style={{ color: 'var(--siecle-beige)', fontSize: 14, fontWeight: 700 }}>
          {fmtPrice(product.price)}
        </p>
      </Link>
    </motion.article>
  )
}
