import { motion } from 'framer-motion'
import WatchOptionGroup from './WatchOptionGroup'
import WatchCustomizationSummary from './WatchCustomizationSummary'
import {
  watchCustomizationOptions,
  watchGroupLabels,
  watchGroupOrder,
  calcPriceDelta,
} from '../data/watchCustomizationOptions'

const fmt = (n) => Number(n).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

export default function WatchCustomizerPanel({
  productName,
  basePrice,
  customization,
  stockQty,
  adding,
  added,
  error,
  onOptionChange,
  onAddToCart,
}) {
  const optionsDelta = calcPriceDelta(customization)
  const finalPrice = parseFloat(basePrice || 0) + optionsDelta

  return (
    <motion.aside
      className="watch-customizer-panel"
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* Header */}
      <div className="watch-customizer-header">
        <p className="watch-customizer-eyebrow">Configurateur SIÈCLE</p>
        <h2 className="watch-customizer-title">{productName}</h2>
        <p className="watch-customizer-price">
          {fmt(finalPrice)}
          {optionsDelta > 0 && (
            <span className="watch-customizer-price-delta">
              (base {fmt(basePrice)} + options {fmt(optionsDelta)})
            </span>
          )}
        </p>
      </div>

      {/* Option groups */}
      <div className="watch-option-groups">
        {watchGroupOrder.map(group => (
          <WatchOptionGroup
            key={group}
            groupKey={group}
            label={watchGroupLabels[group]}
            options={watchCustomizationOptions[group]}
            selectedId={customization[group]}
            onSelect={onOptionChange}
          />
        ))}
      </div>

      {/* Summary + CTA */}
      <WatchCustomizationSummary
        customization={customization}
        basePrice={basePrice}
        stockQty={stockQty}
        adding={adding}
        added={added}
        error={error}
        onAdd={onAddToCart}
      />
    </motion.aside>
  )
}
