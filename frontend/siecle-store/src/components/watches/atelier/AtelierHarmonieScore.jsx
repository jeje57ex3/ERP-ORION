import { motion } from 'framer-motion'

export default function AtelierHarmonieScore({ score }) {
  const color = score >= 95 ? '#D8C7A3' : score >= 88 ? '#C9A96E' : '#9A8A72'

  return (
    <div className="atelier-harmony">
      <div className="atelier-harmony-top">
        <span>Harmonie SIÈCLE</span>
        <strong style={{ color }}>{score}%</strong>
      </div>
      <div className="atelier-harmony-bar">
        <motion.span
          style={{ backgroundColor: color }}
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
      <p className="atelier-harmony-label">
        {score >= 95 ? 'Composition d\'exception' : score >= 88 ? 'Équilibre remarquable' : 'Bonne composition'}
      </p>
    </div>
  )
}
