import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'

function CartLine({ item, onRemove, onQtyChange }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      style={{
        display: 'flex', gap: '1rem', padding: '1.25rem 0',
        borderBottom: '1px solid var(--color-border)',
      }}
    >
      <div style={{
        width: 80, height: 80, flexShrink: 0, borderRadius: 'var(--radius)',
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        overflow: 'hidden',
      }}>
        {item.image
          ? <img src={item.image} alt={item.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          : <div style={{ width: '100%', height: '100%', background: 'var(--color-border)' }} />}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontFamily: 'var(--font-heading)', fontSize: '0.95rem', marginBottom: 4 }}>{item.name}</p>
        {item.variant && <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>{item.variant}</p>}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            border: '1px solid var(--color-border)', borderRadius: 'var(--radius)',
            padding: '2px 8px',
          }}>
            <button onClick={() => onQtyChange(item.id, item.quantity - 1)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: 'var(--color-text)', padding: '0 4px' }}>−</button>
            <span style={{ fontSize: 14, minWidth: 24, textAlign: 'center' }}>{item.quantity}</span>
            <button onClick={() => onQtyChange(item.id, item.quantity + 1)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: 'var(--color-text)', padding: '0 4px' }}>+</button>
          </div>
          <button onClick={() => onRemove(item.id)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 12, color: 'var(--color-text-muted)', textDecoration: 'underline' }}>
            Supprimer
          </button>
        </div>
      </div>

      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>
          {Number((item.price || 0) * item.quantity).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
        </p>
        {item.quantity > 1 && (
          <p style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
            {Number(item.price || 0).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })} / unité
          </p>
        )}
      </div>
    </motion.div>
  )
}

export default function LuneaPanier() {
  const [cart, setCart] = useState(null)
  const [loading, setLoading] = useState(true)
  const [checkoutLoading, setCheckoutLoading] = useState(false)

  const fetchCart = useCallback(() => {
    fetch('/api/v1/lunea/cart/', { credentials: 'include' })
      .then(r => r.ok ? r.json() : null)
      .then(d => setCart(d))
      .catch(() => setCart(null))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    document.title = 'Mon panier — LUNEA'
    fetchCart()
  }, [fetchCart])

  function handleRemove(lineId) {
    fetch('/api/v1/lunea/cart/', {
      method: 'DELETE',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ line_id: lineId }),
    }).then(fetchCart)
  }

  function handleQtyChange(lineId, qty) {
    if (qty < 1) { handleRemove(lineId); return }
    fetch('/api/v1/lunea/cart/add/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ line_id: lineId, quantity: qty }),
    }).then(fetchCart)
  }

  async function handleCheckout() {
    setCheckoutLoading(true)
    try {
      const res = await fetch('/api/v1/lunea/checkout/session/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brand_key: 'lunea' }),
      })
      const data = await res.json()
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      }
    } catch {
      /* ignore */
    } finally {
      setCheckoutLoading(false)
    }
  }

  const items = cart?.lines ?? []
  const total = items.reduce((s, l) => s + (l.price || 0) * l.quantity, 0)
  const count = items.reduce((s, l) => s + l.quantity, 0)

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      <section className="lunea-section">
        <div className="lunea-container" style={{ maxWidth: 960 }}>
          <p className="lunea-eyebrow">Boutique</p>
          <h1 className="lunea-heading" style={{ marginBottom: '2.5rem' }}>
            Mon panier {count > 0 && <span style={{ fontSize: '1rem', fontWeight: 400, color: 'var(--color-text-muted)' }}>({count} article{count > 1 ? 's' : ''})</span>}
          </h1>

          {loading ? (
            <p style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '4rem' }}>Chargement...</p>
          ) : items.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '4rem' }}>
              <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.2rem', marginBottom: '1rem' }}>Votre panier est vide</p>
              <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: '2rem' }}>Découvrez nos produits et commencez votre rituel LUNEA.</p>
              <Link to="/lunea/boutique/" className="btn-primary">Découvrir la boutique</Link>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '2.5rem', alignItems: 'start' }}>
              <div>
                <AnimatePresence>
                  {items.map(item => (
                    <CartLine key={item.id} item={item} onRemove={handleRemove} onQtyChange={handleQtyChange} />
                  ))}
                </AnimatePresence>
                <div style={{ marginTop: '1.5rem' }}>
                  <Link to="/lunea/boutique/" style={{ fontSize: 13, color: 'var(--color-text-muted)', textDecoration: 'underline' }}>
                    ← Continuer mes achats
                  </Link>
                </div>
              </div>

              <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: '1.5rem', position: 'sticky', top: 'calc(var(--header-h) + 1rem)' }}>
                <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', fontWeight: 400, marginBottom: '1.25rem' }}>Résumé</h3>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: 14 }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>Sous-total</span>
                  <span>{total.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem', fontSize: 14, color: 'var(--color-text-muted)' }}>
                  <span>Livraison</span>
                  <span>calculée à l'étape suivante</span>
                </div>
                <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '1rem', display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-heading)', fontSize: '1.1rem', marginBottom: '1.5rem' }}>
                  <span>Total</span>
                  <span>{total.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}</span>
                </div>
                <button
                  className="btn-primary"
                  onClick={handleCheckout}
                  disabled={checkoutLoading}
                  style={{ width: '100%', textAlign: 'center' }}
                >
                  {checkoutLoading ? 'Redirection...' : 'Commander'}
                </button>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
