import { motion } from 'framer-motion'

export default function WatchHotspot({ part, index, isActive, onActivate }) {
  return (
    <motion.button
      className={`watch-hotspot${isActive ? ' active' : ''}`}
      style={{
        left: `${part.position.x}%`,
        top: `${part.position.y}%`,
      }}
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ delay: 0.6 + index * 0.08, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      onClick={() => onActivate(part.id)}
      onMouseEnter={() => onActivate(part.id)}
      title={part.label}
      aria-label={`Point ${part.label}`}
    >
      {/* Pulse ring */}
      {isActive && (
        <motion.span
          style={{
            position: 'absolute',
            inset: -8,
            borderRadius: '50%',
            border: '1px solid rgba(216,199,163,0.4)',
          }}
          animate={{ scale: [1, 1.6, 1], opacity: [0.6, 0, 0.6] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}
    </motion.button>
  )
}
