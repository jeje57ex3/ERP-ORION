import { motion } from 'framer-motion'
import {
  watchCustomizationOptions,
  watchGroupLabels,
  watchGroupOrder,
  getOption,
  calcPriceDelta,
} from '../data/watchCustomizationOptions'

const fmt = (n) => Number(n).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

export default function WatchCustomizationSummary({
  customization,
  basePrice,
  stockQty = 0,
  adding,
  added,
  error,
  onAdd,
}) {
  const optionsDelta = calcPriceDelta(customization)
  const finalPrice = parseFloat(basePrice || 0) + optionsDelta

  const stockBadge = stockQty > 10
    ? { cls: 'ok',  label: 'En stock' }
    : stockQty > 0
      ? { cls: 'low', label: `Dernières pièces (${stockQty})` }
      : { cls: 'empty', label: 'Épuisé' }

  return (
    <div className="watch-summary">
      <p className="watch-summary-title">Récapitulatif</p>

      {watchGroupOrder.map(group => {
        const opt = getOption(group, customization[group])
        if (!opt) return null
        return (
          <div key={group} className="watch-summary-row">
            <span className="watch-summary-key">{watchGroupLabels[group]}</span>
            <span className="watch-summary-val" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                background: opt.color, border: '1px solid rgba(255,255,255,0.2)',
              }} />
              {opt.label}
              {opt.priceDelta > 0 && (
                <span style={{ fontSize: 10, color: '#d8c7a3' }}>+{opt.priceDelta} €</span>
              )}
            </span>
          </div>
        )
      })}

      <hr className="watch-summary-divider" />

      <div className="watch-summary-row">
        <span className="watch-summary-key">Base</span>
        <span className="watch-summary-val">{fmt(basePrice)}</span>
      </div>
      {optionsDelta > 0 && (
        <div className="watch-summary-row">
          <span className="watch-summary-key">Options</span>
          <span className="watch-summary-val">+{fmt(optionsDelta)}</span>
        </div>
      )}

      <div className="watch-summary-total">
        <span className="watch-summary-total-label">Total</span>
        <span className="watch-summary-total-price">{fmt(finalPrice)}</span>
      </div>

      <span className={`watch-stock-badge ${stockBadge.cls}`}>{stockBadge.label}</span>

      {error && <div className="watch-validate-error">{error}</div>}

      <motion.button
        className={`watch-add-button${added ? ' added' : ''}`}
        onClick={onAdd}
        disabled={adding || stockQty === 0}
        whileTap={stockQty > 0 ? { scale: 0.98 } : undefined}
      >
        {added
          ? '✓ Montre ajoutée au panier'
          : adding
            ? 'Validation…'
            : stockQty === 0
              ? 'Épuisé'
              : 'Ajouter ma montre personnalisée'}
      </motion.button>
    </div>
  )
}
