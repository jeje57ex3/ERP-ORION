import { motion } from 'framer-motion'

export default function Loader({ text = 'SIÈCLE' }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#000',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      zIndex: 9999,
    }}>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          fontFamily: 'Montserrat, Inter, sans-serif',
          fontSize: 28,
          fontWeight: 900,
          letterSpacing: '0.2em',
          color: '#fff',
          marginBottom: 24,
        }}
      >
        {text}
      </motion.div>
      <div style={{ width: 120, height: 1, background: '#2A2A2A', position: 'relative', overflow: 'hidden' }}>
        <motion.div
          animate={{ x: ['-100%', '200%'] }}
          transition={{ repeat: Infinity, duration: 1.2, ease: 'easeInOut' }}
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
