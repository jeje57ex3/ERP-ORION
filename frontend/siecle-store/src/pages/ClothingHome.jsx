import { useEffect, useState } from 'react'
import PremiumHero from '../components/PremiumHero'
import EditorialSection from '../components/EditorialSection'
import ProductGrid from '../components/ProductGrid'
import { getProducts } from '../api/products'

export default function ClothingHome() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getProducts({ category: 'vetements', limit: 8 })
      .then(d => setProducts(d.results))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ background: '#000' }}>
      <PremiumHero
        title="VÊTEMENTS"
        slogan="SILHOUETTES — MATIÈRES — SOIN"
        subtitle="Des pièces essentielles conçues pour durer. Chaque coupe pensée pour le quotidien, chaque matière choisie pour la durabilité."
        secondaryBtn="VOIR LA COLLECTION"
        secondaryLink="/boutique?categorie=vetements"
      />

      <EditorialSection
        eyebrow="L'ESSENTIEL REVISITÉ"
        title="COUPES INTEMPORELLES"
        text="Chez SIÈCLE, le vêtement est un signal d'identité. Ni tendance, ni classique — simplement juste. Des silhouettes propres qui s'intègrent naturellement dans n'importe quelle garde-robe."
        btnLabel="EXPLORER LA BOUTIQUE"
        btnLink="/boutique?categorie=vetements"
      >
        <div style={{
          background: 'linear-gradient(135deg, #111 0%, #1A1A1A 100%)',
          aspectRatio: '3/4',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 96, fontWeight: 900, color: 'rgba(200,184,154,0.06)',
          }}>V</span>
        </div>
      </EditorialSection>

      <EditorialSection
        eyebrow="FABRICATION"
        title="DES MATIÈRES QUI DURENT"
        text="Coton biologique, lin naturel, jersey doux. Nous sélectionnons nos matières pour leur confort quotidien et leur résistance au temps — pas pour leur label."
        reverse
      >
        <div style={{
          background: '#111', aspectRatio: '3/4',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: 24, padding: 40,
        }}>
          {['Coton biologique', 'Lin naturel', 'Jersey doux', 'Denim traité'].map(m => (
            <div key={m} style={{
              borderBottom: '1px solid rgba(200,184,154,0.12)',
              paddingBottom: 16, width: '100%', textAlign: 'center',
              color: 'rgba(255,255,255,0.45)', fontSize: 13, letterSpacing: '0.1em',
            }}>
              {m}
            </div>
          ))}
        </div>
      </EditorialSection>

      {/* Products */}
      <section style={{ padding: '80px 24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: 56 }}>
            <p style={{ color: '#C8B89A', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 12 }}>
              LA COLLECTION
            </p>
            <h2 style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(22px, 3.5vw, 40px)', fontWeight: 900, color: '#fff',
            }}>
              VÊTEMENTS
            </h2>
          </div>
          <ProductGrid products={products} loading={loading} />
        </div>
      </section>
    </div>
  )
}
