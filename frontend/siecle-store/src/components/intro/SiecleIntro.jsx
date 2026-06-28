import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function SiecleIntro({ onDone }) {
  const [phase, setPhase] = useState('in') // in | hold | out

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('hold'), 600)
    const t2 = setTimeout(() => setPhase('out'),  1200)
    const t3 = setTimeout(() => onDone?.(),        1800)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3) }
  }, [onDone])

  return (
    <AnimatePresence>
      {phase !== 'done' && (
        <motion.div
          key="intro"
          initial={{ opacity: 1 }}
          animate={{ opacity: phase === 'out' ? 0 : 1 }}
          transition={{ duration: 0.55, ease: 'easeInOut' }}
          style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: '#050505',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: 20,
          }}
        >
          {/* Logo */}
          <motion.p
            initial={{ opacity: 0, y: 10, letterSpacing: '0.6em' }}
            animate={{ opacity: 1,  y: 0,  letterSpacing: '0.28em' }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
            style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(28px, 6vw, 52px)',
              fontWeight: 900,
              color: '#fff',
              letterSpacing: '0.28em',
              margin: 0,
            }}
          >
            SIÈCLE
          </motion.p>

          {/* Ligne fine animée */}
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: 48 }}
            transition={{ duration: 0.6, delay: 0.35, ease: [0.22, 1, 0.36, 1] }}
            style={{ height: 1, background: 'var(--siecle-beige, #C0A882)' }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
