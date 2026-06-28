import { motion, AnimatePresence } from 'framer-motion'
import { Link } from 'react-router-dom'
import { useCart } from '../hooks/useCart'

const fmt = (p) => Number(p).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

export default function CartSidebar() {
  const { isOpen, setIsOpen, items, removeItem, updateQty, total } = useCart()

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={() => setIsOpen(false)}
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.7)',
              zIndex: 1100,
            }}
          />

          {/* Drawer */}
          <motion.aside
            key="drawer"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            style={{
              position: 'fixed', top: 0, right: 0, bottom: 0,
              width: 400, maxWidth: '100vw',
              background: '#0D0D0D',
              borderLeft: '1px solid rgba(255,255,255,0.08)',
              zIndex: 1101,
              display: 'flex', flexDirection: 'column',
            }}
          >
            {/* Header */}
            <div style={{
              padding: '20px 24px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div>
                <p style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.14em', color: 'var(--siecle-beige)' }}>
                  PANIER
                </p>
                <p style={{ color: 'var(--siecle-muted)', fontSize: 12, marginTop: 2 }}>
                  {items.length} article{items.length !== 1 ? 's' : ''}
                </p>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                style={{ background: 'none', border: 'none', color: 'var(--siecle-muted)', fontSize: 20, cursor: 'pointer' }}
              >
                ×
              </button>
            </div>

            {/* Items */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px' }}>
              {items.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '60px 0' }}>
                  <p style={{ color: 'var(--siecle-muted)', fontSize: 14 }}>Votre panier est vide</p>
                  <button
                    onClick={() => setIsOpen(false)}
                    style={{
                      marginTop: 20, padding: '12px 24px',
                      border: '1px solid rgba(255,255,255,0.15)',
                      background: 'none', color: '#fff', cursor: 'pointer',
                      fontSize: 11, fontWeight: 700, letterSpacing: '0.1em',
                    }}
                  >
                    CONTINUER LE SHOPPING
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  {items.map((item) => (
                    <div key={`${item.id}-${item.size || ''}`} style={{
                      display: 'flex', gap: 14,
                      paddingBottom: 20,
                      borderBottom: '1px solid rgba(255,255,255,0.05)',
                    }}>
                      {/* Thumbnail */}
                      <div style={{
                        width: 80, height: 100, flexShrink: 0,
                        background: '#1A1A1A', overflow: 'hidden',
                      }}>
                        {item.image && (
                          <img src={item.image} alt={item.name}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                        )}
                      </div>

                      {/* Details */}
                      <div style={{ flex: 1 }}>
                        <p style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 4 }}>
                          {item.name}
                        </p>
                        {item.size && !item.isCustomWatch && (
                          <p style={{ fontSize: 11, color: 'var(--siecle-muted)', marginBottom: 6 }}>
                            Taille: {item.size}
                          </p>
                        )}
                        {/* Customized watch details */}
                        {item.isCustomWatch && item.customizationLabels && (
                          <div style={{ marginBottom: 6 }}>
                            {Object.entries(item.customizationLabels).map(([key, val]) => (
                              <p key={key} style={{ fontSize: 10, color: 'var(--siecle-muted)', lineHeight: 1.6, margin: 0 }}>
                                {key === 'case' ? 'Boîtier' : key === 'dial' ? 'Cadran' : key === 'hands' ? 'Aiguilles' : 'Bracelet'}: {val}
                              </p>
                            ))}
                          </div>
                        )}
                        <p style={{ fontSize: 13, color: 'var(--siecle-beige)', fontWeight: 700, marginBottom: 10 }}>
                          {fmt(item.price)}
                        </p>

                        {/* Qty controls */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
                            <button
                              onClick={() => updateQty(item.id, item.size, item.qty - 1)}
                              style={{
                                width: 28, height: 28, background: '#1A1A1A',
                                border: '1px solid rgba(255,255,255,0.1)',
                                color: '#fff', cursor: 'pointer', fontSize: 14,
                              }}
                            >−</button>
                            <span style={{
                              width: 36, textAlign: 'center',
                              fontSize: 13, color: '#fff',
                              background: '#111', height: 28, lineHeight: '28px',
                              display: 'inline-block',
                              borderTop: '1px solid rgba(255,255,255,0.1)',
                              borderBottom: '1px solid rgba(255,255,255,0.1)',
                            }}>
                              {item.qty}
                            </span>
                            <button
                              onClick={() => updateQty(item.id, item.size, item.qty + 1)}
                              style={{
                                width: 28, height: 28, background: '#1A1A1A',
                                border: '1px solid rgba(255,255,255,0.1)',
                                color: '#fff', cursor: 'pointer', fontSize: 14,
                              }}
                            >+</button>
                          </div>
                          <button
                            onClick={() => removeItem(item.id, item.size)}
                            style={{
                              background: 'none', border: 'none',
                              color: 'var(--siecle-muted)', cursor: 'pointer',
                              fontSize: 11, letterSpacing: '0.08em',
                            }}
                          >
                            Supprimer
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            {items.length > 0 && (
              <div style={{
                padding: '20px 24px',
                borderTop: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ color: 'var(--siecle-muted)', fontSize: 12 }}>Sous-total</span>
                  <span style={{ color: '#fff', fontSize: 14, fontWeight: 700 }}>{fmt(total)}</span>
                </div>
                <p style={{ color: 'var(--siecle-muted)', fontSize: 11, marginBottom: 20 }}>
                  Livraison calculée au checkout
                </p>
                <Link to="/cart" onClick={() => setIsOpen(false)}
                  style={{
                    display: 'block', width: '100%', padding: '14px 0',
                    background: 'var(--siecle-beige)', color: '#000',
                    textAlign: 'center', fontWeight: 800,
                    fontSize: 12, letterSpacing: '0.14em',
                    marginBottom: 10,
                  }}
                >
                  VOIR LE PANIER
                </Link>
                <p style={{ textAlign: 'center', color: 'var(--siecle-muted)', fontSize: 11 }}>
                  Paiement sécurisé · Stripe
                </p>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  )
}
