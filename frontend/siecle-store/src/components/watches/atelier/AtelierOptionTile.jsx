import { motion } from 'framer-motion'

export default function AtelierOptionTile({ option, type, isSelected, onClick }) {
  return (
    <motion.button
      type="button"
      className={`atelier-option-tile${isSelected ? ' is-selected' : ''}`}
      onClick={onClick}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.97 }}
      transition={{ duration: 0.18 }}
    >
      {type === 'color' && (
        <span
          className="atelier-color-dot"
          style={{
            backgroundColor: option.color,
            boxShadow: isSelected ? `0 0 0 2px rgba(216,199,163,0.6)` : 'none',
          }}
        />
      )}
      {type === 'choice' && (
        <span className={`atelier-choice-mark${isSelected ? ' is-selected' : ''}`} />
      )}
      <span className="atelier-option-label">{option.label}</span>
      {option.priceDelta > 0 && (
        <span className="atelier-option-price">+{option.priceDelta} €</span>
      )}
    </motion.button>
  )
}
