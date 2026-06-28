import { motion } from 'framer-motion'

const ICONS = { vetements: '👕', montres: '⌚', maquillage: '💄' }

export default function SearchResultCard({ result, onClick }) {
  return (
    <motion.a href={`/produit/${result.slug || result.id}`} onClick={onClick}
      className="search-result-card"
      whileHover={{ backgroundColor: 'rgba(255,255,255,0.05)' }}
      style={{ display: 'flex', alignItems: 'center', gap: 16, padding: 16, borderRadius: 14, cursor: 'pointer', textDecoration: 'none', marginBottom: 4 }}>
      <div style={{ width: 56, height: 56, borderRadius: 10, background: '#111', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24, flexShrink: 0, overflow: 'hidden' }}>
        {result.image ? <img src={result.image} alt={result.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : ICONS[result.category] || '📦'}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: '#fff', marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{result.name}</div>
        <div style={{ fontSize: 11, color: '#555', letterSpacing: '0.1em', textTransform: 'uppercase' }}>{result.category}</div>
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--siecle-beige)', whiteSpace: 'nowrap', flexShrink: 0 }}>{result.price} €</div>
    </motion.a>
  )
}
