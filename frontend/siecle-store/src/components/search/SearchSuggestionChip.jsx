import { motion } from 'framer-motion'

export default function SearchSuggestionChip({ label, onClick, icon }) {
  return (
    <motion.button whileHover={{ borderColor: 'var(--siecle-beige)', color: 'var(--siecle-beige)' }} whileTap={{ scale: 0.96 }}
      onClick={() => onClick?.(label)}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 16px', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 999, color: '#aaa', fontSize: 12, fontWeight: 600, cursor: 'pointer', background: 'transparent', transition: 'all 0.2s', letterSpacing: '0.06em', fontFamily: 'inherit' }}>
      {icon && <span>{icon}</span>}
      {label}
    </motion.button>
  )
}
