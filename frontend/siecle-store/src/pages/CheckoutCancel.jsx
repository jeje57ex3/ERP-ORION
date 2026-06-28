import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import MotionPage from '../components/MotionPage'

export default function CheckoutCancel() {
  return (
    <MotionPage style={{
      paddingTop: 'var(--header-h)', minHeight: '100vh',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{ textAlign: 'center', padding: '0 24px', maxWidth: 480 }}>
        {/* X circle */}
        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 160, damping: 14, delay: 0.2 }}
          style={{
            width: 80, height: 80, borderRadius: '50%',
            background: 'rgba(255,100,100,0.1)',
            border: '2px solid rgba(255,100,100,0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 32px', fontSize: 32, color: '#FF6464',
          }}
        >
          ×
        </motion.div>

        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.4 } }}
          style={{ color: '#FF9090', fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', marginBottom: 12 }}
        >
          PAIEMENT ANNULÉ
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.5 } }}
          style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 'clamp(24px, 4vw, 36px)', fontWeight: 900,
            color: '#fff', marginBottom: 16, letterSpacing: '0.04em',
          }}
        >
          VOTRE PAIEMENT A ÉTÉ ANNULÉ
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { delay: 0.65 } }}
          style={{ color: 'var(--siecle-muted)', fontSize: 14, lineHeight: 1.8, marginBottom: 40 }}
        >
          Ne vous inquiétez pas — votre panier a été conservé.
          Vous pouvez reprendre votre commande à tout moment.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0, transition: { delay: 0.8 } }}
          style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap' }}
        >
          <Link to="/cart" style={{
            padding: '14px 32px', background: 'var(--siecle-beige)', color: '#000',
            fontSize: 12, fontWeight: 800, letterSpacing: '0.14em',
          }}>
            RETOUR AU PANIER
          </Link>
          <Link to="/shop" style={{
            padding: '14px 32px', border: '1px solid rgba(255,255,255,0.15)',
            color: '#fff', fontSize: 12, fontWeight: 800, letterSpacing: '0.14em',
            background: 'transparent',
          }}>
            BOUTIQUE
          </Link>
        </motion.div>
      </div>
    </MotionPage>
  )
}
