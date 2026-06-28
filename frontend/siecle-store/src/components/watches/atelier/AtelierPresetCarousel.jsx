import { motion } from 'framer-motion'

export default function AtelierPresetCarousel({ presets, onApply }) {
  return (
    <div className="atelier-preset-carousel">
      <p className="atelier-preset-label">Presets SIÈCLE</p>
      <div className="atelier-preset-list">
        {presets.map(preset => (
          <motion.button
            key={preset.id}
            type="button"
            className="atelier-preset-chip"
            onClick={() => onApply(preset)}
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.97 }}
            transition={{ duration: 0.18 }}
            title={preset.description}
          >
            <span className="atelier-preset-name">{preset.name}</span>
          </motion.button>
        ))}
      </div>
    </div>
  )
}
