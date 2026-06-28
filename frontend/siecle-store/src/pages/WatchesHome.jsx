import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PremiumHero from '../components/PremiumHero'
import WatchAnatomyAnimation from '../components/WatchAnatomyAnimation'
import WatchManufacturingTimeline from '../components/WatchManufacturingTimeline'
import ProductGrid from '../components/ProductGrid'
import { getProducts } from '../api/products'

export default function WatchesHome() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    document.title = 'Montres SIÈCLE — Design minimaliste, précision artisanale'
    let desc = document.querySelector('meta[name="description"]')
    if (!desc) { desc = document.createElement('meta'); desc.name = 'description'; document.head.appendChild(desc) }
    desc.content = 'Découvrez les montres SIÈCLE : un design épuré, des matériaux de qualité et un savoir-faire artisanal.'
    return () => { document.title = 'SIÈCLE' }
  }, [])

  useEffect(() => {
    getProducts({ category: 'montres', limit: 8 })
      .then(d => setProducts(d.results ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <div style={{ background: '#000' }}>
        <PremiumHero
          title="MONTRES"
          slogan="DESIGN — PRÉCISION — IDENTITÉ"
          subtitle="Une montre SIÈCLE, c'est un signal minimaliste au poignet. Ni ostentatoire, ni anonyme — distincte."
          primaryBtn="ANATOMIE DE LA MONTRE"
          onScrollTarget="anatomie"
          secondaryBtn="VOIR LES MONTRES"
          secondaryLink="/boutique?categorie=montres"
        />

        {/* Watch anatomy interactive section */}
        <WatchAnatomyAnimation />

        {/* Manufacturing timeline */}
        <WatchManufacturingTimeline />

        {/* Atelier SIÈCLE CTA */}
        <section style={{
          padding: '96px 24px', background: '#080808', textAlign: 'center',
          position: 'relative', overflow: 'hidden',
        }}>
          {/* Background glow */}
          <div style={{
            position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
            width: 600, height: 300, borderRadius: '50%',
            background: 'radial-gradient(ellipse, rgba(216,199,163,0.08) 0%, transparent 70%)',
            pointerEvents: 'none',
          }} />

          <p style={{ position: 'relative', color: '#D8C7A3', fontSize: 10, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 20, textTransform: 'uppercase' }}>
            Exclusivité SIÈCLE — Configurateur Atelier
          </p>
          <h2 style={{ position: 'relative', fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(22px, 3.5vw, 44px)', fontWeight: 900, color: '#fff', letterSpacing: '0.04em', marginBottom: 20 }}>
            ATELIER SIÈCLE
          </h2>
          <p style={{ position: 'relative', color: '#B8B8B8', fontSize: 15, maxWidth: 520, margin: '0 auto 12px', lineHeight: 1.7 }}>
            Composez votre montre signature pièce par pièce.
          </p>
          <p style={{ position: 'relative', color: '#7A7060', fontSize: 13, maxWidth: 480, margin: '0 auto 36px' }}>
            Boîtier · Cadran · Aiguilles · Bracelet · Gravure — prévisualisés en direct.
          </p>

          <Link to="/montres/atelier"
            style={{
              position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 12,
              background: '#D8C7A3', color: '#000',
              fontFamily: 'Montserrat, sans-serif', fontSize: 11, fontWeight: 900, letterSpacing: '0.16em',
              textTransform: 'uppercase', padding: '18px 44px',
              textDecoration: 'none', transition: 'all 0.25s ease',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = '#D8C7A3'; e.currentTarget.style.boxShadow = '0 0 0 1px #D8C7A3 inset' }}
            onMouseLeave={e => { e.currentTarget.style.background = '#D8C7A3'; e.currentTarget.style.color = '#000'; e.currentTarget.style.boxShadow = 'none' }}
          >
            ENTRER DANS L'ATELIER →
          </Link>
        </section>

        {/* Products */}
        <section style={{ padding: '96px 24px', background: '#000' }} id="collection">
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ textAlign: 'center', marginBottom: 56 }}>
              <p style={{ color: '#D8C7A3', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 12 }}>
                LA COLLECTION
              </p>
              <h2 style={{
                fontFamily: 'Montserrat, sans-serif',
                fontSize: 'clamp(22px, 3.5vw, 40px)', fontWeight: 900, color: '#fff',
                letterSpacing: '0.04em',
              }}>
                MONTRES SIÈCLE
              </h2>
            </div>
            <ProductGrid products={products} loading={loading} />
          </div>
        </section>
      </div>
    </>
  )
}

