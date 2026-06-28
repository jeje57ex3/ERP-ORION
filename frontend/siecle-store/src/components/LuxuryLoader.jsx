import { motion } from 'framer-motion'

export default function LuxuryLoader({ text = 'SIÈCLE' }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#000',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      zIndex: 9999,
    }}>
      <motion.p
        initial={{ opacity: 0, letterSpacing: '0.4em' }}
        animate={{ opacity: 1, letterSpacing: '0.25em' }}
        transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
        style={{
          fontFamily: 'Montserrat, sans-serif',
          fontSize: 26, fontWeight: 900,
          color: '#fff', marginBottom: 28,
        }}
      >
        {text}
      </motion.p>

      <div style={{ width: 80, height: 1, background: 'rgba(255,255,255,0.08)', position: 'relative', overflow: 'hidden' }}>
        <motion.div
          animate={{ x: ['-100%', '200%'] }}
          transition={{ repeat: Infinity, duration: 1.4, ease: 'easeInOut' }}
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '50%', height: '100%',
            background: 'linear-gradient(90deg, transparent, #D8C7A3, transparent)',
          }}
        />
      </div>
    </div>
  )
}
