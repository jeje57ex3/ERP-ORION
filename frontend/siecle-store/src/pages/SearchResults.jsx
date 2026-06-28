import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { staggerContainer, fadeUp } from '../utils/animations'
import PageTransition from '../components/PageTransition'

export default function SearchResults() {
  const [params]  = useSearchParams()
  const query     = params.get('q') || ''
  const [results, setResults]  = useState(null)
  const [loading, setLoading]  = useState(false)

  useEffect(() => {
    if (!query.trim()) { setResults([]); return }
    setLoading(true)
    fetch(`/api/v1/siecle/search/?q=${encodeURIComponent(query)}`)
      .then(r => r.ok ? r.json() : { results: [] })
      .then(data => setResults(data.results || []))
      .catch(() => setResults([]))
      .finally(() => setLoading(false))
  }, [query])

  return (
    <PageTransition>
      <div style={{ minHeight: '60vh', padding: '80px 24px', maxWidth: 1200, margin: '0 auto' }}>
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          style={{ marginBottom: 56 }}
        >
          <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.24em', color: 'var(--siecle-beige)', marginBottom: 12 }}>
            RÉSULTATS
          </p>
          <h1 style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 'clamp(22px, 4vw, 40px)',
            fontWeight: 900, color: '#fff',
            letterSpacing: '0.04em',
          }}>
            {query ? `"${query}"` : 'Recherche'}
          </h1>
          {!loading && results && (
            <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: 13, marginTop: 10 }}>
              {results.length === 0
                ? 'Aucun résultat trouvé'
                : `${results.length} résultat${results.length > 1 ? 's' : ''}`}
            </p>
          )}
        </motion.div>

        {/* Loader */}
        {loading && (
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center', padding: '80px 0' }}>
            {[0, 1, 2].map(i => (
              <motion.div
                key={i}
                style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--siecle-beige)' }}
                animate={{ y: [0, -10, 0] }}
                transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }}
              />
            ))}
          </div>
        )}

        {/* Results */}
        {!loading && results && results.length > 0 && (
          <motion.div
            variants={staggerContainer}
            initial="hidden"
            animate="visible"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 24 }}
          >
            {results.map((item, i) => (
              <motion.div key={i} variants={fadeUp}>
                <Link
                  to={item.url || '#'}
                  style={{ display: 'block', textDecoration: 'none' }}
                >
                  <div style={{
                    background: '#111',
                    border: '1px solid rgba(255,255,255,0.06)',
                    padding: 24,
                    transition: 'border-color 0.2s',
                  }}
                    onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(192,168,130,0.3)'}
                    onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'}
                  >
                    {item.image && (
                      <div style={{ aspectRatio: '4/3', background: '#1a1a1a', marginBottom: 16, overflow: 'hidden' }}>
                        <img src={item.image} alt={item.title}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      </div>
                    )}
                    <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.16em', color: 'var(--siecle-beige)', marginBottom: 8 }}>
                      {(item.type || 'PRODUIT').toUpperCase()}
                    </p>
                    <p style={{ fontFamily: 'Montserrat, sans-serif', fontWeight: 700, color: '#fff', fontSize: 14, marginBottom: 6 }}>
                      {item.title}
                    </p>
                    {item.subtitle && (
                      <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>{item.subtitle}</p>
                    )}
                    {item.price && (
                      <p style={{ color: 'var(--siecle-beige)', fontWeight: 700, fontSize: 14, marginTop: 10 }}>
                        {item.price} €
                      </p>
                    )}
                  </div>
                </Link>
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* No results */}
        {!loading && results && results.length === 0 && query && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            style={{ textAlign: 'center', padding: '60px 0' }}
          >
            <p style={{ color: 'rgba(255,255,255,0.25)', fontSize: 48, marginBottom: 24 }}>○</p>
            <p style={{ color: '#fff', fontFamily: 'Montserrat, sans-serif', fontWeight: 700, fontSize: 18, marginBottom: 12 }}>
              Aucun résultat pour "{query}"
            </p>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, marginBottom: 36 }}>
              Essayez un autre terme ou explorez nos collections.
            </p>
            <Link to="/boutique" style={{
              display: 'inline-block', padding: '12px 32px',
              background: 'var(--siecle-beige)', color: '#000',
              fontSize: 11, fontWeight: 800, letterSpacing: '0.14em',
              textDecoration: 'none',
            }}>
              VOIR LA BOUTIQUE
            </Link>
          </motion.div>
        )}
      </div>
    </PageTransition>
  )
}
