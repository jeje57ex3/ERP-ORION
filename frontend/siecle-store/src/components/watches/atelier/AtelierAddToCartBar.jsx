import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { addCustomWatchToCart } from '../../../api/watches'

const fmt = n => Number(n).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'

export default function AtelierAddToCartBar({ configuration, price, harmonyScore }) {
  const [state, setState] = useState('idle') // idle | loading | success | error

  async function handleAddToCart() {
    setState('loading')
    try {
      await addCustomWatchToCart({
        brand_key: 'siecle',
        base_product_slug: 'classic-date',
        configuration,
        price,
        harmony_score: harmonyScore,
      })

      window.dispatchEvent(new CustomEvent('siecle-cart-updated', {
        detail: { type: 'custom_watch', name: configuration.creationName, price: price.total },
      }))

      setState('success')
      setTimeout(() => setState('idle'), 3000)
    } catch {
      setState('error')
      setTimeout(() => setState('idle'), 2500)
    }
  }

  const btnLabel = {
    idle:    'Ajouter au panier',
    loading: 'Ajout en cours...',
    success: 'Ajouté au panier ✓',
    error:   'Erreur — réessayer',
  }[state]

  return (
    <div className="atelier-cart-bar">
      <div className="atelier-cart-bar__creation">
        <span>Votre création</span>
        <strong>{configuration.creationName || 'Ma Signature SIÈCLE'}</strong>
      </div>

      <div className="atelier-cart-bar__price">
        <span>Total</span>
        <strong>{fmt(price.total)}</strong>
      </div>

      <motion.button
        type="button"
        className={`atelier-cart-bar__btn atelier-cart-bar__btn--${state}`}
        onClick={handleAddToCart}
        disabled={state === 'loading'}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
      >
        {btnLabel}
      </motion.button>
    </div>
  )
}
