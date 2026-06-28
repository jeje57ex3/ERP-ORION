import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import MotionPage from '../components/MotionPage'
import { useCart } from '../hooks/useCart'

export default function CheckoutSuccess() {
  const [searchParams] = useSearchParams()
  const { clearCart } = useCart()
  const sessionId = searchParams.get('session_id')

  useEffect(() => { clearCart() }, [])

  return (
    <MotionPage style={{
      paddingTop: 'var(--header-h)', minHeight: '100vh',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{ textAlign: 'center', padding: '0 24px', maxWidth: 520 }}>
        {/* Check circle */}
        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 160, damping: 14, delay: 0.2 }}
          style={{
            width: 80, height: 80, borderRadius: '50%',
            background: 'rgba(111, 208, 140, 0.15)',
            border: '2px solid rgba(111, 208, 140, 0.6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 32px', fontSize: 32,
          }}
        >
          ✓
        </motion.div>

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.4 } }}
          style={{ color: '#6FD08C', fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', marginBottom: 12 }}
        >
          COMMANDE CONFIRMÉE
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.5 } }}
          style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 'clamp(26px, 4vw, 40px)', fontWeight: 900,
            color: '#fff', marginBottom: 16, letterSpacing: '0.04em',
          }}
        >
          MERCI POUR VOTRE COMMANDE
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { delay: 0.65 } }}
          style={{ color: 'var(--siecle-muted)', fontSize: 14, lineHeight: 1.8, marginBottom: 8 }}
        >
          Votre paiement a été traité avec succès.
          Un e-mail de confirmation vous sera envoyé prochainement.
        </motion.p>

        {sessionId && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { delay: 0.75 } }}
            style={{ color: 'rgba(255,255,255,0.2)', fontSize: 11, marginBottom: 40, letterSpacing: '0.06em' }}
          >
            Session: {sessionId.slice(-12)}
          </motion.p>
        )}

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.85 } }}
          style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap' }}
        >
          <Link to="/shop" style={{
            padding: '14px 32px', background: 'var(--siecle-beige)', color: '#000',
            fontSize: 12, fontWeight: 800, letterSpacing: '0.14em',
          }}>
            CONTINUER LE SHOPPING
          </Link>
          <Link to="/" style={{
            padding: '14px 32px', border: '1px solid rgba(255,255,255,0.15)',
            color: '#fff', fontSize: 12, fontWeight: 800, letterSpacing: '0.14em',
            background: 'transparent',
          }}>
            ACCUEIL
          </Link>
        </motion.div>
      </div>
    </MotionPage>
  )
}
