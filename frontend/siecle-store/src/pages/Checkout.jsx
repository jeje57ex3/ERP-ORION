import { useState } from 'react'
import { motion } from 'framer-motion'
import { useCart } from '../hooks/useCart'
import PageTransition from '../components/PageTransition'

export default function Checkout() {
  const { items, total, clearCart } = useCart()
  const [step, setStep] = useState(1)
  const [form, setForm] = useState({
    email: '', firstName: '', lastName: '', address: '', city: '', zip: '', country: 'FR',
    sameAsBilling: true, giftPackaging: false, giftMessage: '', promoCode: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const update = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const { apiPost } = await import('../api/apiClient')
      const res = await apiPost('/api/v1/siecle/create-checkout-session/', {
        items: items.map(i => ({ id: i.id, qty: i.quantity, customization: i.customization })),
        customer: form,
        gift_packaging: form.giftPackaging,
        gift_message: form.giftMessage,
        promo_code: form.promoCode,
      })
      if (res.url) window.location.href = res.url
      else setError('Erreur lors de la création de la session de paiement.')
    } catch {
      setError('Une erreur est survenue. Veuillez réessayer.')
    } finally {
      setLoading(false)
    }
  }

  const s = {
    page: { minHeight: '100vh', background: '#000', paddingTop: 100, paddingBottom: 80 },
    wrap: { maxWidth: 1100, margin: '0 auto', padding: '0 24px', display: 'grid', gridTemplateColumns: '1fr 380px', gap: 48 },
    title: { fontSize: 32, fontWeight: 900, letterSpacing: '0.08em', color: '#fff', marginBottom: 40 },
    section: { background: '#111', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 28, marginBottom: 24 },
    sectionTitle: { fontSize: 13, fontWeight: 700, letterSpacing: '0.16em', color: 'var(--siecle-beige)', marginBottom: 20, textTransform: 'uppercase' },
    field: { marginBottom: 18 },
    label: { display: 'block', fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', color: '#888', marginBottom: 8, textTransform: 'uppercase' },
    input: { width: '100%', background: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '12px 16px', color: '#fff', fontSize: 14, outline: 'none' },
    row2: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 },
    check: { display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', marginBottom: 12 },
    btn: { width: '100%', padding: '16px 24px', background: '#fff', color: '#000', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer' },
    summary: { background: '#111', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 28, position: 'sticky', top: 100 },
    itemRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' },
    error: { background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '12px 16px', color: '#fca5a5', fontSize: 13, marginBottom: 16 },
  }

  return (
    <PageTransition>
      <div style={s.page}>
        <div style={s.wrap}>
          <div>
            <h1 style={s.title}>CHECKOUT</h1>
            {error && <div style={s.error}>{error}</div>}
            <form onSubmit={handleSubmit}>
              {/* Contact */}
              <div style={s.section}>
                <div style={s.sectionTitle}>Coordonnées</div>
                <div style={s.field}>
                  <label style={s.label}>Email</label>
                  <input style={s.input} type="email" required value={form.email} onChange={e => update('email', e.target.value)} placeholder="votre@email.com" />
                </div>
                <div style={{ ...s.row2 }}>
                  <div style={s.field}><label style={s.label}>Prénom</label><input style={s.input} required value={form.firstName} onChange={e => update('firstName', e.target.value)} /></div>
                  <div style={s.field}><label style={s.label}>Nom</label><input style={s.input} required value={form.lastName} onChange={e => update('lastName', e.target.value)} /></div>
                </div>
              </div>

              {/* Livraison */}
              <div style={s.section}>
                <div style={s.sectionTitle}>Adresse de livraison</div>
                <div style={s.field}><label style={s.label}>Adresse</label><input style={s.input} required value={form.address} onChange={e => update('address', e.target.value)} placeholder="12 rue de la Paix" /></div>
                <div style={s.row2}>
                  <div style={s.field}><label style={s.label}>Code postal</label><input style={s.input} required value={form.zip} onChange={e => update('zip', e.target.value)} /></div>
                  <div style={s.field}><label style={s.label}>Ville</label><input style={s.input} required value={form.city} onChange={e => update('city', e.target.value)} /></div>
                </div>
              </div>

              {/* Options cadeau */}
              <div style={s.section}>
                <div style={s.sectionTitle}>Options cadeau</div>
                <label style={s.check}>
                  <input type="checkbox" checked={form.giftPackaging} onChange={e => update('giftPackaging', e.target.checked)} />
                  <span style={{ color: '#fff', fontSize: 14 }}>Emballage cadeau SIÈCLE (+5,90 €)</span>
                </label>
                {form.giftPackaging && (
                  <div style={s.field}>
                    <label style={s.label}>Message cadeau</label>
                    <textarea style={{ ...s.input, height: 80, resize: 'vertical' }} value={form.giftMessage} onChange={e => update('giftMessage', e.target.value)} placeholder="Votre message personnalisé..." />
                  </div>
                )}
                <div style={s.field}>
                  <label style={s.label}>Code promo</label>
                  <input style={s.input} value={form.promoCode} onChange={e => update('promoCode', e.target.value)} placeholder="SIECLE2025" />
                </div>
              </div>

              <button type="submit" style={s.btn} disabled={loading}>
                {loading ? 'REDIRECTION...' : 'PAYER MAINTENANT →'}
              </button>
            </form>
          </div>

          {/* Résumé commande */}
          <div style={s.summary}>
            <div style={s.sectionTitle}>Votre commande</div>
            {items.length === 0 ? (
              <p style={{ color: '#888', fontSize: 14 }}>Panier vide</p>
            ) : (
              items.map(item => (
                <div key={item.id} style={s.itemRow}>
                  <div>
                    <div style={{ color: '#fff', fontSize: 14, fontWeight: 600 }}>{item.name}</div>
                    <div style={{ color: '#888', fontSize: 12 }}>Qté : {item.quantity}</div>
                  </div>
                  <div style={{ color: 'var(--siecle-beige)', fontWeight: 700 }}>{(item.price * item.quantity).toFixed(2)} €</div>
                </div>
              ))
            )}
            {form.giftPackaging && (
              <div style={s.itemRow}>
                <span style={{ color: '#ccc', fontSize: 13 }}>Emballage cadeau</span>
                <span style={{ color: 'var(--siecle-beige)' }}>5,90 €</span>
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20, paddingTop: 20, borderTop: '1px solid rgba(255,255,255,0.12)' }}>
              <span style={{ color: '#fff', fontWeight: 800, fontSize: 16 }}>TOTAL</span>
              <span style={{ color: '#fff', fontWeight: 900, fontSize: 18 }}>
                {(total + (form.giftPackaging ? 5.9 : 0)).toFixed(2)} €
              </span>
            </div>
            <div style={{ marginTop: 16, fontSize: 11, color: '#666', textAlign: 'center' }}>
              Paiement sécurisé par Stripe
            </div>
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
