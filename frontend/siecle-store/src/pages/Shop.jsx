import { useState, useEffect, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import MotionPage from '../components/MotionPage'
import ProductGrid from '../components/ProductGrid'
import Loader from '../components/Loader'
import UniverseCard from '../components/UniverseCard'
import { getProducts, getCollections } from '../api/products'

const UNIVERSES = [
  { slug: 'vetements',  title: 'Vêtements',  description: 'Silhouettes minimalistes, matières durables.', link: '/vetements' },
  { slug: 'montres',    title: 'Montres',    description: 'Design épuré, identité forte.',              link: '/montres' },
  { slug: 'maquillage', title: 'Maquillage', description: 'Formules douces, teintes inclusives.',       link: '/maquillage' },
]

const SORT_OPTIONS = [
  { value: '',         label: 'Par défaut' },
  { value: 'price',   label: 'Prix croissant' },
  { value: '-price',  label: 'Prix décroissant' },
  { value: '-created_at', label: 'Nouveautés' },
  { value: 'name',    label: 'Nom A-Z' },
]

export default function Shop() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [products,    setProducts]    = useState([])
  const [collections, setCollections] = useState([])
  const [loading,     setLoading]     = useState(true)
  const [total,       setTotal]       = useState(0)

  const category = searchParams.get('category') || ''
  const sort     = searchParams.get('sort')     || ''
  const search   = searchParams.get('q')        || ''

  const fetchProducts = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (category) params.category = category
      if (sort)     params.ordering = sort
      if (search)   params.search   = search
      const data = await getProducts(params)
      const list = Array.isArray(data) ? data : (data.results ?? [])
      setProducts(list)
      setTotal(data.count ?? list.length)
    } finally {
      setLoading(false)
    }
  }, [category, sort, search])

  useEffect(() => { fetchProducts() }, [fetchProducts])
  useEffect(() => { getCollections().then(d => setCollections(d.results ?? d)) }, [])

  const setParam = (key, val) => {
    const next = new URLSearchParams(searchParams)
    if (val) next.set(key, val)
    else next.delete(key)
    setSearchParams(next)
  }

  return (
    <MotionPage style={{ paddingTop: 'var(--header-h)', minHeight: '100vh' }}>
      <div style={{ maxWidth: 1440, margin: '0 auto', padding: '40px 24px 80px' }}>

        {/* Universe entry cards (only when no category filter active) */}
        {!category && (
          <div style={{ marginBottom: 60 }}>
            <p style={{ color: 'var(--siecle-beige)', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 20 }}>
              NOS UNIVERS
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }} className="universe-entry-grid">
              {UNIVERSES.map((u, i) => (
                <UniverseCard key={u.slug} {...u} index={i} />
              ))}
            </div>
          </div>
        )}

        {/* Page header */}
        <div style={{ marginBottom: 40, paddingBottom: 32, borderBottom: '1px solid rgba(241,237,229,0.06)' }}>
          <p style={{ color: 'var(--siecle-beige)', fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', marginBottom: 8 }}>
            SIÈCLE
          </p>
          <h1 style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(28px, 4vw, 48px)', fontWeight: 900,
            letterSpacing: '0.04em', color: 'var(--siecle-white)',
          }}>
            {category ? category.toUpperCase() : 'BOUTIQUE'}
          </h1>
          {total > 0 && (
            <p style={{ color: 'var(--siecle-muted)', fontSize: 12, marginTop: 8 }}>
              {total} produit{total !== 1 ? 's' : ''}
            </p>
          )}
        </div>

        <div style={{ display: 'flex', gap: 48, alignItems: 'flex-start' }}>
          {/* Sidebar filters */}
          <aside style={{ width: 200, flexShrink: 0 }} className="siecle-shop-sidebar">
            {/* Categories */}
            <div style={{ marginBottom: 36 }}>
              <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.16em', color: 'rgba(241,237,229,0.4)', marginBottom: 16 }}>
                CATÉGORIES
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <button
                  onClick={() => setParam('category', '')}
                  style={{
                    textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer',
                    fontSize: 13, fontWeight: category === '' ? 700 : 400,
                    color: category === '' ? 'var(--siecle-beige)' : 'var(--siecle-muted)',
                    letterSpacing: '0.04em',
                  }}
                >
                  Tout
                </button>
                {collections.map(col => (
                  <button key={col.slug || col.id}
                    onClick={() => setParam('category', col.slug)}
                    style={{
                      textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer',
                      fontSize: 13, fontWeight: category === col.slug ? 700 : 400,
                      color: category === col.slug ? 'var(--siecle-beige)' : 'var(--siecle-muted)',
                      letterSpacing: '0.04em',
                    }}
                  >
                    {col.name}
                  </button>
                ))}
              </div>
            </div>
          </aside>

          {/* Main content */}
          <div style={{ flex: 1 }}>
            {/* Toolbar */}
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              marginBottom: 32, flexWrap: 'wrap', gap: 12,
            }}>
              {/* Search */}
              <input
                type="search" placeholder="Rechercher..."
                defaultValue={search}
                onChange={e => setParam('q', e.target.value)}
                style={{
                  padding: '10px 16px', background: 'rgba(241,237,229,0.05)',
                  border: '1px solid rgba(241,237,229,0.1)', borderRadius: 'var(--radius-input)',
                  color: 'var(--siecle-white)', fontSize: 13, width: 220,
                  outline: 'none',
                }}
              />
              {/* Sort */}
              <select
                value={sort}
                onChange={e => setParam('sort', e.target.value)}
                style={{
                  padding: '10px 16px', background: 'var(--siecle-dark)',
                  border: '1px solid rgba(241,237,229,0.1)', borderRadius: 'var(--radius-input)',
                  color: 'var(--siecle-white)', fontSize: 12, cursor: 'pointer',
                  outline: 'none',
                }}
              >
                {SORT_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {/* Grid */}
            {loading ? (
              <div style={{ padding: '80px 0', textAlign: 'center' }}>
                <Loader text="Chargement..." />
              </div>
            ) : products.length === 0 ? (
              <div style={{ padding: '80px 0', textAlign: 'center' }}>
                <p style={{ color: 'var(--siecle-muted)', fontSize: 15 }}>Aucun produit trouvé</p>
              </div>
            ) : (
              <ProductGrid products={products} columns={3} />
            )}
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .siecle-shop-sidebar { display: none; }
          .universe-entry-grid { grid-template-columns: 1fr !important; }
        }
        @media (max-width: 900px) {
          .universe-entry-grid { grid-template-columns: repeat(2, 1fr) !important; }
        }
      `}</style>
    </MotionPage>
  )
}
