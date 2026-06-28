import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import PageTransition from '../components/PageTransition'
import { useCart } from '../hooks/useCart'

const DESIGNS = [
  { id: 'noir-signature', label: 'Noir Signature', bg: 'linear-gradient(135deg,#0a0a0a,#1a1a1a)', accent: '#D8C7A3', border: '#2a2a2a' },
  { id: 'beige-elegance', label: 'Beige Élégance', bg: 'linear-gradient(135deg,#e8d8c3,#f7f2ea)', accent: '#3a2a1f', border: '#c8ad8b' },
  { id: 'dore-nuit',      label: 'Doré Nuit',      bg: 'linear-gradient(135deg,#1a1400,#2d2200)', accent: '#c9a45c', border: '#c9a45c' },
  { id: 'minimal-blanc',  label: 'Minimal Blanc',  bg: 'linear-gradient(135deg,#f8f8f8,#ffffff)', accent: '#111', border: '#ddd' },
]
const AMOUNTS = [25, 50, 100, 150, 200, 300]

export default function GiftCardAnimated() {
  const [design, setDesign]     = useState(DESIGNS[0])
  const [amount, setAmount]     = useState(50)
  const [custom, setCustom]     = useState('')
  const [recipient, setRecipient] = useState('')
  const [message, setMessage]   = useState('')
  const [flipped, setFlipped]   = useState(false)
  const [added, setAdded]       = useState(false)
  const { addItem }             = useCart()

  const finalAmount = custom ? parseFloat(custom) || 0 : amount

  const handleAdd = () => {
    addItem?.({ id: `giftcard-${design.id}-${finalAmount}`, name: `Carte cadeau SIÈCLE — ${finalAmount} €`, price: finalAmount, quantity: 1, type: 'giftcard', meta: { design: design.id, recipient, message } })
    setAdded(true)
    setTimeout(() => setAdded(false), 2500)
  }

  const s = {
    page: { minHeight: '100vh', background: '#000', paddingTop: 100, paddingBottom: 80 },
    wrap: { maxWidth: 1100, margin: '0 auto', padding: '0 24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 64, alignItems: 'start' },
    title: { fontSize: 36, fontWeight: 900, letterSpacing: '0.08em', color: '#fff', marginBottom: 8 },
    sub: { color: '#888', fontSize: 14, marginBottom: 40 },
    label: { fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', color: 'var(--siecle-beige)', textTransform: 'uppercase', display: 'block', marginBottom: 12 },
    section: { marginBottom: 28 },
    designs: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 },
    designBtn: (active) => ({ background: active ? 'rgba(216,199,163,0.1)' : '#111', border: `1px solid ${active ? 'var(--siecle-beige)' : 'rgba(255,255,255,0.1)'}`, borderRadius: 10, padding: '10px 14px', cursor: 'pointer', color: active ? 'var(--siecle-beige)' : '#ccc', fontSize: 12, fontWeight: 600, textAlign: 'left', transition: 'all 0.2s' }),
    amounts: { display: 'flex', flexWrap: 'wrap', gap: 10 },
    amountBtn: (active) => ({ background: active ? '#fff' : '#111', border: `1px solid ${active ? '#fff' : 'rgba(255,255,255,0.1)'}`, borderRadius: 8, padding: '10px 18px', cursor: 'pointer', color: active ? '#000' : '#ccc', fontSize: 14, fontWeight: 700, transition: 'all 0.2s' }),
    input: { width: '100%', background: '#111', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '12px 16px', color: '#fff', fontSize: 14, outline: 'none' },
    btn: { width: '100%', padding: '16px 24px', background: added ? '#22c55e' : '#fff', color: added ? '#fff' : '#000', border: 'none', borderRadius: 10, fontSize: 13, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer', transition: 'all 0.3s', marginTop: 8 },
  }

  return (
    <PageTransition>
      <div style={s.page}>
        <div style={s.wrap}>
          {/* Config panel */}
          <div>
            <h1 style={s.title}>CARTE CADEAU</h1>
            <p style={s.sub}>Offrez l'univers SIÈCLE.</p>

            <div style={s.section}>
              <label style={s.label}>Design</label>
              <div style={s.designs}>
                {DESIGNS.map(d => (
                  <button key={d.id} style={s.designBtn(design.id === d.id)} onClick={() => setDesign(d)}>{d.label}</button>
                ))}
              </div>
            </div>

            <div style={s.section}>
              <label style={s.label}>Montant</label>
              <div style={s.amounts}>
                {AMOUNTS.map(a => (
                  <button key={a} style={s.amountBtn(amount === a && !custom)} onClick={() => { setAmount(a); setCustom('') }}>{a} €</button>
                ))}
              </div>
              <input style={{ ...s.input, marginTop: 10 }} type="number" placeholder="Montant personnalisé..." value={custom} onChange={e => setCustom(e.target.value)} min={5} max={1000} />
            </div>

            <div style={s.section}>
              <label style={s.label}>Pour</label>
              <input style={s.input} placeholder="Destinataire (optionnel)" value={recipient} onChange={e => setRecipient(e.target.value)} />
            </div>

            <div style={s.section}>
              <label style={s.label}>Message</label>
              <textarea style={{ ...s.input, height: 90, resize: 'vertical' }} placeholder="Votre message personnalisé..." value={message} onChange={e => setMessage(e.target.value)} />
            </div>

            <button style={s.btn} onClick={handleAdd}>
              {added ? '✓ AJOUTÉE AU PANIER' : `AJOUTER AU PANIER — ${finalAmount} €`}
            </button>
          </div>

          {/* Carte animée */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 24, position: 'sticky', top: 100 }}>
            <div style={{ perspective: 1200, cursor: 'pointer' }} onClick={() => setFlipped(f => !f)}>
              <motion.div
                animate={{ rotateY: flipped ? 180 : 0 }}
                transition={{ duration: 0.7, ease: [0.22,1,0.36,1] }}
                style={{ width: 380, height: 240, transformStyle: 'preserve-3d', position: 'relative' }}
              >
                {/* Recto */}
                <div style={{ position: 'absolute', inset: 0, backfaceVisibility: 'hidden', borderRadius: 20, background: design.bg, border: `1px solid ${design.border}`, padding: 32, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', boxShadow: '0 40px 80px rgba(0,0,0,0.5)' }}>
                  <div style={{ fontSize: 24, fontWeight: 900, letterSpacing: '0.2em', color: design.accent }}>SIÈCLE</div>
                  <div>
                    {recipient && <div style={{ color: design.accent, fontSize: 12, marginBottom: 4, opacity: 0.7 }}>Pour {recipient}</div>}
                    <div style={{ fontSize: 40, fontWeight: 900, color: design.accent }}>{finalAmount} €</div>
                  </div>
                  <div style={{ fontSize: 10, letterSpacing: '0.14em', color: design.accent, opacity: 0.5 }}>CARTE CADEAU • SIECLE.FR</div>
                </div>
                {/* Verso */}
                <div style={{ position: 'absolute', inset: 0, backfaceVisibility: 'hidden', transform: 'rotateY(180deg)', borderRadius: 20, background: design.bg, border: `1px solid ${design.border}`, padding: 32, display: 'flex', flexDirection: 'column', justifyContent: 'center', boxShadow: '0 40px 80px rgba(0,0,0,0.5)' }}>
                  <div style={{ fontSize: 11, color: design.accent, opacity: 0.7, marginBottom: 12, letterSpacing: '0.1em' }}>MESSAGE</div>
                  <div style={{ fontSize: 14, color: design.accent, lineHeight: 1.6 }}>{message || 'Votre message apparaîtra ici…'}</div>
                  <div style={{ marginTop: 24, fontSize: 9, color: design.accent, opacity: 0.4, letterSpacing: '0.2em' }}>CODE : XXXX-XXXX-XXXX</div>
                </div>
              </motion.div>
            </div>
            <p style={{ color: '#555', fontSize: 12 }}>Cliquez pour retourner la carte</p>
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
