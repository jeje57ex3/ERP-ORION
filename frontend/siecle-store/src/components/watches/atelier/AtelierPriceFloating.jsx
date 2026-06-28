import { motion, AnimatePresence } from 'framer-motion'

const fmt = n => Number(n).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

export default function AtelierPriceFloating({ price, visible = true }) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="atelier-price-floating"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          transition={{ duration: 0.3 }}
        >
          <span className="atelier-price-floating__label">Total</span>
          <strong className="atelier-price-floating__value">{fmt(price.total)}</strong>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
