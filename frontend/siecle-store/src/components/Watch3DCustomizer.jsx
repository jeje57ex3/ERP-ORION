import { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import Watch3DModel from './Watch3DModel'
import WatchCustomizerPanel from './WatchCustomizerPanel'
import {
  defaultWatchCustomization,
  watchGroupLabels,
  watchGroupOrder,
  getOption,
  calcPriceDelta,
} from '../data/watchCustomizationOptions'
import { useCart } from '../hooks/useCart'
import '../styles/watch-customizer.css'

const fmt = (n) => Number(n).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

export default function Watch3DCustomizer({ product, basePrice, modelUrl, fallbackImage }) {
  const [customization, setCustomization] = useState(defaultWatchCustomization)
  const [adding, setAdding]   = useState(false)
  const [added, setAdded]     = useState(false)
  const [error, setError]     = useState(null)
  const { addItem, setIsOpen } = useCart()

  const optionsDelta = calcPriceDelta(customization)
  const finalPrice   = parseFloat(basePrice || 0) + optionsDelta

  const handleOptionChange = useCallback((group, id) => {
    setCustomization(prev => ({ ...prev, [group]: id }))
    setError(null)
    setAdded(false)
  }, [])

  const handleAddToCart = async () => {
    if (adding || added) return
    setAdding(true)
    setError(null)

    // Server-side validation: recompute price on backend
    try {
      const configPayload = {
        case:  customization.case,
        dial:  customization.dial,
        hands: customization.hands,
        strap: customization.strap,
      }

      const res = await fetch(
        `/api/v1/siecle/products/${product.slug}/validate-customization/`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ customization: configPayload }),
        }
      )

      let validated = { final_price: finalPrice, options_price: optionsDelta }
      if (res.ok) {
        try { validated = await res.json() } catch {}
      } else if (res.status !== 404) {
        // 404 means endpoint not yet deployed — use frontend calc
        const err = await res.json().catch(() => ({}))
        setError(err.detail || err.error || 'Configuration invalide. Veuillez vérifier vos options.')
        setAdding(false)
        return
      }

      // Build customization labels
      const labels = {}
      watchGroupOrder.forEach(group => {
        const opt = getOption(group, customization[group])
        if (opt) labels[group] = opt.label
      })

      // Add to cart — use a unique key that includes the config hash
      const configStr = JSON.stringify(customization)
      const cartItem = {
        id:    `${product.id}__custom__${btoa(configStr).slice(0, 12)}`,
        slug:  product.slug,
        name:  `${product.name} — Personnalisée`,
        price: String(validated.final_price ?? finalPrice),
        image: product.image || fallbackImage || null,
        // Extended fields for customized watches
        isCustomWatch:       true,
        customization:       configPayload,
        customizationLabels: labels,
        base_price:          parseFloat(basePrice),
        options_price:       validated.options_price ?? optionsDelta,
        final_price:         validated.final_price   ?? finalPrice,
        productId:           product.id,
      }

      addItem(cartItem, '')
      setAdded(true)
      setTimeout(() => setIsOpen(true), 300)
      setTimeout(() => setAdded(false), 3500)
    } catch (e) {
      console.warn('[Watch3DCustomizer] Add to cart error:', e)
      setError('Une erreur est survenue. Veuillez réessayer.')
    } finally {
      setAdding(false)
    }
  }

  return (
    <section className="watch-customizer" aria-label="Configurateur montre SIÈCLE">
      <div className="watch-customizer-container">

        {/* Left: 3D stage */}
        <motion.div
          className="watch-3d-stage"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8 }}
        >
          <Watch3DModel
            modelUrl={modelUrl}
            fallbackImage={fallbackImage}
            customization={customization}
          />
          {!modelUrl && (
            <span className="watch-3d-hint">
              ↻ Changez les options pour voir les couleurs
            </span>
          )}
        </motion.div>

        {/* Right: panel */}
        <WatchCustomizerPanel
          productName={product?.name || 'Montre SIÈCLE'}
          basePrice={basePrice}
          customization={customization}
          stockQty={product?.stock_quantity ?? 0}
          adding={adding}
          added={added}
          error={error}
          onOptionChange={handleOptionChange}
          onAddToCart={handleAddToCart}
        />
      </div>

      {/* Mobile sticky bar */}
      <div className="watch-mobile-sticky">
        <span className="watch-mobile-sticky-price">{fmt(finalPrice)}</span>
        <motion.button
          className={`watch-add-button${added ? ' added' : ''}`}
          style={{ flex: 1, marginTop: 0, minHeight: 46 }}
          onClick={handleAddToCart}
          disabled={adding || (product?.stock_quantity ?? 0) === 0}
          whileTap={{ scale: 0.97 }}
        >
          {added ? '✓ Ajoutée' : adding ? 'Validation…' : 'Ajouter au panier'}
        </motion.button>
      </div>
    </section>
  )
}
