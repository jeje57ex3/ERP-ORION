import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../../styles/premium-search.css'

const SUGGESTIONS = ['T-shirt noir', 'Montre Urban', 'Veste premium', 'Fond de teint', 'Hoodie oversize', 'Jean slim', 'Bracelet cuir']
const ICON_MAP = { vetements: '👕', montres: '⌚', maquillage: '💄' }

export default function PremiumSearchExperience({ onClose }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const inputRef = useRef()

  useEffect(() => { inputRef.current?.focus() }, [])

  useEffect(() => {
    if (!query.trim()) { setResults([]); return }
    const t = setTimeout(async () => {
      setLoading(true)
      try {
        const { search } = await import('../../api/search')
        const data = await search(query)
        setResults(data.results || [])
      } catch {
        const { getAllProducts } = await import('../../data/demoProducts')
        const q = query.toLowerCase()
        setResults(getAllProducts().filter(p => p.name.toLowerCase().includes(q)).slice(0, 6))
      } finally {
        setLoading(false)
      }
    }, 300)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <AnimatePresence>
      <motion.div className="search-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={e => e.target === e.currentTarget && onClose()}>
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
          style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div className="search-input-wrap">
            <input ref={inputRef} className="search-input-premium" value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Rechercher un produit, une catégorie…" />
            <button className="search-close" onClick={onClose}>✕</button>
          </div>

          {!query && (
            <div className="search-suggestions">
              {SUGGESTIONS.map(s => (
                <button key={s} className="search-chip" onClick={() => setQuery(s)}>{s}</button>
              ))}
            </div>
          )}

          {loading && <div style={{ color: '#555', fontSize: 12, letterSpacing: '0.2em', marginTop: 32 }}>RECHERCHE…</div>}

          {results.length > 0 && (
            <motion.div className="search-results" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {results.map(r => (
                <a key={r.id} href={`/produit/${r.id}`} className="search-result-card" onClick={onClose}>
                  <div className="search-result-image">{ICON_MAP[r.category] || '📦'}</div>
                  <div>
                    <div className="search-result-name">{r.name}</div>
                    <div className="search-result-category">{r.category}</div>
                  </div>
                  <div className="search-result-price">{r.price} €</div>
                </a>
              ))}
            </motion.div>
          )}

          {query && !loading && results.length === 0 && (
            <div style={{ color: '#444', fontSize: 13, marginTop: 40 }}>Aucun résultat pour « {query} »</div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}
