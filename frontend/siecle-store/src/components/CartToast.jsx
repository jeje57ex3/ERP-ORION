import { AnimatePresence, motion } from 'framer-motion'
import { useCart } from '../hooks/useCart'

export default function CartToast() {
  const { toast } = useCart()

  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          key={toast.id}
          className="cart-toast"
          initial={{ opacity: 0, y: 24, scale: 0.96 }}
          animate={{ opacity: 1, y: 0,  scale: 1 }}
          exit={{ opacity: 0, y: 12, scale: 0.96 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        >
          <div className="cart-toast-check">✓</div>
          <div className="cart-toast-body">
            <p className="cart-toast-title">Produit ajouté au panier</p>
            {toast.name && (
              <p className="cart-toast-name">{toast.name}</p>
            )}
            {toast.points > 0 && (
              <p className="cart-toast-points">
                +{toast.points} point{toast.points > 1 ? 's' : ''} fidélité
              </p>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
