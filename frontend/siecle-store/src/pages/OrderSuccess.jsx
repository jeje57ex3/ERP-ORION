import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useCart } from '../hooks/useCart'

export default function OrderSuccess() {
  const { clearCart } = useCart()
  useEffect(() => { clearCart?.() }, [])

  return (
    <div style={{ minHeight: '100vh', background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <motion.div initial={{ opacity: 0, y: 32 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.22,1,0.36,1] }}
        style={{ textAlign: 'center', padding: 48, maxWidth: 520 }}>
        <div style={{ width: 72, height: 72, borderRadius: '50%', background: 'rgba(216,199,163,0.15)', border: '2px solid var(--siecle-beige)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 32px', fontSize: 32 }}>✓</div>
        <h1 style={{ fontSize: 28, fontWeight: 900, letterSpacing: '0.1em', color: '#fff', marginBottom: 16 }}>COMMANDE CONFIRMÉE</h1>
        <p style={{ color: '#888', fontSize: 15, lineHeight: 1.7, marginBottom: 40 }}>
          Merci pour votre commande SIÈCLE. Vous recevrez un email de confirmation avec les détails et le suivi.
        </p>
        <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link to="/compte/commandes" style={{ padding: '14px 28px', background: '#fff', color: '#000', borderRadius: 8, fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', textDecoration: 'none' }}>MES COMMANDES</Link>
          <Link to="/" style={{ padding: '14px 28px', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 700, letterSpacing: '0.14em', textDecoration: 'none' }}>ACCUEIL</Link>
        </div>
      </motion.div>
    </div>
  )
}
