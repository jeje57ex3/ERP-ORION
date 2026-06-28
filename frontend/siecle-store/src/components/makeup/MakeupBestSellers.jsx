import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useCart } from '../../hooks/useCart'
import { makeupBestSellers } from '../../data/makeupProducts'
import { calculatePointsForProduct, formatPoints } from '../../utils/loyaltyPoints'

/* ── SVG product illustrations ── */
const ProductIllustrations = {
  1: (  // Poudre compacte
    <svg viewBox="0 0 120 120" fill="none">
      <ellipse cx="60" cy="62" rx="42" ry="10" fill="#d4b88a" opacity="0.3" />
      <rect x="20" y="34" width="80" height="56" rx="14" fill="#e8d0b8" stroke="#c8ad8b" strokeWidth="1.5" />
      <rect x="26" y="40" width="68" height="44" rx="10" fill="#f0e0c8" />
      <ellipse cx="60" cy="62" rx="24" ry="22" fill="url(#pc1)" stroke="#c8ad8b" strokeWidth="1" />
      <ellipse cx="60" cy="62" rx="16" ry="14" fill="#d4b08a" opacity="0.5" />
      <ellipse cx="55" cy="57" rx="5" ry="4" fill="#f0d8b8" opacity="0.6" />
      <defs>
        <radialGradient id="pc1" cx="40%" cy="40%" r="60%">
          <stop offset="0%" stopColor="#e8c8a0" />
          <stop offset="100%" stopColor="#c8a070" />
        </radialGradient>
      </defs>
    </svg>
  ),
  2: (  // Fond de teint fluide
    <svg viewBox="0 0 120 140" fill="none">
      <rect x="46" y="16" width="28" height="108" rx="8" fill="#e8d0b8" stroke="#c8ad8b" strokeWidth="1.5" />
      <rect x="46" y="16" width="28" height="20" rx="4" fill="#c8a870" />
      <rect x="50" y="40" width="20" height="70" rx="4" fill="#f0e4d0" opacity="0.7" />
      <ellipse cx="60" cy="132" rx="12" ry="4" fill="#c8ad8b" opacity="0.5" />
      <rect x="52" y="62" width="16" height="1.5" fill="#c8a870" opacity="0.7" />
      <rect x="52" y="72" width="12" height="1" fill="#c8a870" opacity="0.5" />
    </svg>
  ),
  3: (  // Rouge à lèvres
    <svg viewBox="0 0 80 160" fill="none">
      <rect x="24" y="80" width="32" height="72" rx="6" fill="#8a3040" stroke="#6a2030" strokeWidth="1.5" />
      <rect x="28" y="84" width="24" height="60" rx="4" fill="#9e3a4a" />
      <rect x="24" y="36" width="32" height="48" rx="4" fill="#c04858" />
      <path d="M24 36 Q40 16 56 36" fill="#d05868" />
      <ellipse cx="40" cy="34" rx="12" ry="4" fill="#e07888" opacity="0.5" />
      <rect x="28" y="100" width="14" height="1" fill="#c9a45c" opacity="0.5" />
      <ellipse cx="40" cy="150" rx="14" ry="3" fill="#6a2030" opacity="0.3" />
    </svg>
  ),
  4: (  // Mascara volume
    <svg viewBox="0 0 80 160" fill="none">
      <rect x="26" y="20" width="28" height="100" rx="8" fill="#050505" />
      <rect x="30" y="26" width="20" height="88" rx="6" fill="#1a1a1a" />
      <rect x="34" y="30" width="12" height="6" rx="2" fill="#2a2a2a" />
      <rect x="26" y="120" width="28" height="30" rx="6" fill="#8a3040" />
      <rect x="30" y="124" width="20" height="22" rx="4" fill="#c04858" />
      <line x1="40" y1="154" x2="40" y2="162" stroke="#6a2030" strokeWidth="2" />
      <path d="M36 162 Q40 165 44 162" fill="none" stroke="#6a2030" strokeWidth="1.5" />
      <ellipse cx="40" cy="168" rx="10" ry="3" fill="#6a2030" opacity="0.3" />
    </svg>
  ),
  5: (  // Palette fards
    <svg viewBox="0 0 160 100" fill="none">
      <rect x="8" y="10" width="144" height="80" rx="8" fill="#2a1a10" stroke="#1a0a08" strokeWidth="1.5" />
      <rect x="14" y="16" width="132" height="68" rx="6" fill="#1a0e08" />
      {/* 8 color pans */}
      {[0,1,2,3].map(i => (
        <g key={i}>
          <rect x={20 + i * 31} y="22" width="25" height="25" rx="4"
            fill={['#d4b08a','#9e3a4a','#3a2820','#c9a45c'][i]} />
          <rect x={20 + i * 31} y="53" width="25" height="25" rx="4"
            fill={['#e8c8a0','#c06070','#6a4030','#d4b070'][i]} />
        </g>
      ))}
      <ellipse cx="80" cy="100" rx="60" ry="5" fill="#1a0a08" opacity="0.2" />
    </svg>
  ),
}

const cardVariants = {
  hidden: { opacity: 0, y: 30 },
  show: i => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] },
  }),
}

function ProductCard({ product, index }) {
  const { addToCart } = useCart()
  const [added, setAdded] = useState(false)

  const handleAdd = () => {
    addToCart({
      id:    product.id,
      name:  product.name,
      price: product.priceRaw ?? 0,
    })
    setAdded(true)
    setTimeout(() => setAdded(false), 1600)
  }

  return (
    <motion.article
      className="makeup-product-card"
      custom={index}
      variants={cardVariants}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true }}
    >
      <div className="makeup-product-img-wrap">
        <div className="makeup-product-img-inner">
          {ProductIllustrations[product.id] ?? null}
        </div>
      </div>
      <p className="makeup-product-name">{product.name}</p>
      <p className="makeup-product-subtitle">{product.subtitle}</p>
      <p className="makeup-product-price">{product.price}</p>
      <p className="makeup-product-points">
        +{formatPoints(calculatePointsForProduct(product.priceRaw ?? product.price))}
      </p>
      <button
        className="makeup-product-add-btn"
        onClick={handleAdd}
        disabled={added}
      >
        {added ? 'Ajouté ✓' : 'Ajouter au panier'}
      </button>
    </motion.article>
  )
}

export default function MakeupBestSellers() {
  const [products, setProducts] = useState(null)

  useEffect(() => {
    fetch('/api/v1/siecle/products/?category=maquillage&best_seller=true')
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
  }, [])

  return (
    <section className="makeup-bestsellers">
      <div className="beauty-container">
        <motion.h2
          className="beauty-section-title"
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          viewport={{ once: true }}
        >
          Best-Sellers
        </motion.h2>
        <span className="beauty-section-rule" />

        {!products ? (
          <div className="makeup-products-grid">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="makeup-product-card makeup-product-skeleton">
                <div className="makeup-product-img-wrap" />
                <div className="makeup-product-skeleton-line" style={{ width: '70%' }} />
                <div className="makeup-product-skeleton-line" style={{ width: '50%' }} />
              </div>
            ))}
          </div>
        ) : (
          <div className="makeup-products-grid">
            {products.map((p, i) => (
              <ProductCard key={p.id} product={p} index={i} />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
