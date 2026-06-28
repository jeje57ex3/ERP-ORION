import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { loadStripe } from '@stripe/stripe-js'
import MotionPage, { fadeUp } from '../components/MotionPage'
import { useCart } from '../hooks/useCart'
import { createCheckoutSession } from '../api/checkout'

const fmt = (p) => Number(p).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLIC_KEY || '')

export default function Cart() {
  const navigate                     = useNavigate()
  const { items, removeItem, updateQty, total, clearCart } = useCart()
  const [email,     setEmail]        = useState('')
  const [loading,   setLoading]      = useState(false)
  const [error,     setError]        = useState('')

  const handleCheckout = async () => {
    if (!email) { setError('Veuillez entrer votre adresse e-mail.'); return }
    setError('')
    setLoading(true)
    try {
      const stripe = await stripePromise
      const payload = items.map(i => ({
        slug:     i.slug,
        quantity: i.qty,
        size:     i.size || '',
      }))
      const { checkout_url } = await createCheckoutSession(payload, email)
      window.location.href = checkout_url
    } catch (e) {
      setError(e.response?.data?.error || 'Une erreur est survenue. Réessayez.')
    } finally {
      setLoading(false)
    }
  }

  if (items.length === 0) {
    return (
      <MotionPage style={{ paddingTop: 'var(--header-h)', minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', padding: '0 24px' }}>
          <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', color: 'var(--siecle-beige)', marginBottom: 16 }}>PANIER</p>
          <h1 style={{
            fontFamily: 'Montserrat, sans-serif', fontSize: 32, fontWeight: 900,
            color: '#fff', marginBottom: 16, letterSpacing: '0.04em',
          }}>VOTRE PANIER EST VIDE</h1>
          <p style={{ color: 'var(--siecle-muted)', fontSize: 14, marginBottom: 32 }}>
            Découvrez nos collections et ajoutez des articles.
          </p>
          <Link to="/shop" style={{
            padding: '14px 36px', background: 'var(--siecle-beige)', color: '#000',
            fontSize: 12, fontWeight: 800, letterSpacing: '0.14em',
          }}>
            VOIR LA BOUTIQUE
          </Link>
        </div>
      </MotionPage>
    )
  }

  return (
    <MotionPage style={{ paddingTop: 'var(--header-h)', minHeight: '100vh' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '40px 24px 80px' }}>

        <motion.div variants={fadeUp} initial="hidden" animate="visible" style={{ marginBottom: 40 }}>
          <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', color: 'var(--siecle-beige)', marginBottom: 8 }}>SIÈCLE</p>
          <h1 style={{
            fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(28px, 4vw, 44px)',
            fontWeight: 900, color: '#fff', letterSpacing: '0.04em',
          }}>MON PANIER</h1>
        </motion.div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 48, alignItems: 'start' }}
          className="siecle-cart-layout">

          {/* Items */}
          <div>
            {items.map((item, i) => (
              <motion.div
                key={`${item.id}-${item.size || ''}`}
                variants={fadeUp} initial="hidden" animate="visible" custom={i}
                style={{
                  display: 'flex', gap: 20,
                  paddingBottom: 28, marginBottom: 28,
                  borderBottom: '1px solid rgba(255,255,255,0.06)',
                }}
              >
                {/* Thumbnail */}
                <Link to={`/product/${item.slug}`}>
                  <div style={{ width: 100, height: 130, background: '#111', overflow: 'hidden', flexShrink: 0 }}>
                    {item.image && (
                      <img src={item.image} alt={item.name}
                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      />
                    )}
                  </div>
                </Link>

                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                    <div>
                      <p style={{ color: '#fff', fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{item.name}</p>
                      {item.size && (
                        <p style={{ color: 'var(--siecle-muted)', fontSize: 12 }}>Taille: {item.size}</p>
                      )}
                    </div>
                    <button
                      onClick={() => removeItem(item.id, item.size)}
                      style={{ background: 'none', border: 'none', color: 'var(--siecle-muted)', cursor: 'pointer', fontSize: 18, padding: 0 }}
                    >×</button>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 }}>
                    {/* Qty */}
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <button
                        onClick={() => updateQty(item.id, item.size, item.qty - 1)}
                        style={{ width: 32, height: 32, background: '#1A1A1A', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer' }}
                      >−</button>
                      <span style={{
                        width: 40, textAlign: 'center', fontSize: 13, color: '#fff',
                        background: '#111', height: 32, lineHeight: '32px', display: 'inline-block',
                        borderTop: '1px solid rgba(255,255,255,0.1)', borderBottom: '1px solid rgba(255,255,255,0.1)',
                      }}>{item.qty}</span>
                      <button
                        onClick={() => updateQty(item.id, item.size, item.qty + 1)}
                        style={{ width: 32, height: 32, background: '#1A1A1A', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer' }}
                      >+</button>
                    </div>
                    <p style={{ color: 'var(--siecle-beige)', fontSize: 16, fontWeight: 700 }}>
                      {fmt(item.price * item.qty)}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Summary */}
          <motion.div
            variants={fadeUp} initial="hidden" animate="visible" custom={3}
            style={{
              background: '#0D0D0D', border: '1px solid rgba(255,255,255,0.06)',
              padding: 28,
              position: 'sticky', top: 'calc(var(--header-h) + 24px)',
            }}
          >
            <p style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', color: '#fff', marginBottom: 24 }}>
              RÉCAPITULATIF
            </p>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ color: 'var(--siecle-muted)', fontSize: 13 }}>Sous-total ({items.reduce((a, i) => a + i.qty, 0)} articles)</span>
              <span style={{ color: '#fff', fontSize: 13, fontWeight: 600 }}>{fmt(total)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
              <span style={{ color: 'var(--siecle-muted)', fontSize: 13 }}>Livraison</span>
              <span style={{ color: 'var(--siecle-muted)', fontSize: 13 }}>Calculée au checkout</span>
            </div>
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 16, marginBottom: 24 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#fff', fontSize: 15, fontWeight: 700 }}>Total</span>
                <span style={{ color: 'var(--siecle-beige)', fontSize: 18, fontWeight: 700 }}>{fmt(total)}</span>
              </div>
            </div>

            {/* Email */}
            <input
              type="email" placeholder="Votre e-mail"
              value={email} onChange={e => setEmail(e.target.value)}
              style={{
                width: '100%', padding: '12px 14px', marginBottom: 12,
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: '#fff', fontSize: 13, boxSizing: 'border-box',
                outline: 'none',
              }}
            />

            {error && (
              <p style={{ color: '#FF6464', fontSize: 12, marginBottom: 12 }}>{error}</p>
            )}

            <button
              onClick={handleCheckout}
              disabled={loading}
              style={{
                width: '100%', padding: '16px 0',
                background: loading ? '#555' : 'var(--siecle-beige)',
                color: '#000', border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: 12, fontWeight: 800, letterSpacing: '0.14em',
                marginBottom: 12,
              }}
            >
              {loading ? 'REDIRECTION...' : 'PASSER LA COMMANDE'}
            </button>
            <p style={{ textAlign: 'center', color: 'var(--siecle-muted)', fontSize: 11 }}>
              Paiement sécurisé · SSL · Stripe
            </p>
          </motion.div>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .siecle-cart-layout { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </MotionPage>
  )
}
