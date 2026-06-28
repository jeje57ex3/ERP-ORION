import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import PremiumHero from '../components/PremiumHero'
import UniverseCard from '../components/UniverseCard'
import EditorialSection from '../components/EditorialSection'
import ProductCard from '../components/ProductCard'
import { getProducts } from '../api/products'

const UNIVERSES = [
  {
    slug: 'vetements',
    title: 'Vêtements',
    description: 'Silhouettes propres, matières douces. Des pièces pensées pour la vie quotidienne.',
    link: '/vetements',
  },
  {
    slug: 'montres',
    title: 'Montres',
    description: 'Design minimaliste, accessibilité assumée. La montre comme signal d\'identité.',
    link: '/montres',
  },
  {
    slug: 'maquillage',
    title: 'Maquillage',
    description: 'Formules douces et éthiques. Des teintes conçues pour toutes les carnations.',
    link: '/maquillage',
    newTab: true,
  },
]

export default function LandingHome() {
  const [featured, setFeatured] = useState([])
  const universesRef = useRef(null)

  useEffect(() => {
    getProducts({ featured: true, limit: 4 }).then(d => setFeatured(d.results.slice(0, 4))).catch(() => {})
  }, [])

  return (
    <div style={{ background: '#000' }}>
      <PremiumHero
        title="SIÈCLE"
        slogan="MODE — MONTRES — MAQUILLAGE"
        subtitle="Des collections pensées pour celles et ceux qui ne cherchent pas à en faire trop — juste à bien le faire."
        primaryBtn="EXPLORER"
        onScrollTarget="universes"
        secondaryBtn="BOUTIQUE"
        secondaryLink="/boutique"
      />

      {/* Universes */}
      <section id="universes" style={{ padding: '100px 24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            style={{ textAlign: 'center', marginBottom: 64 }}
          >
            <p style={{ color: 'var(--siecle-beige)', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 14 }}>
              NOS UNIVERS
            </p>
            <h2 style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(26px, 4vw, 48px)', fontWeight: 900, color: '#fff',
            }}>
              ENTREZ DANS VOTRE UNIVERS
            </h2>
          </motion.div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }} className="universe-grid">
            {UNIVERSES.map((u, i) => (
              <UniverseCard key={u.slug} {...u} index={i} tall />
            ))}
          </div>
        </div>
      </section>

      {/* Editorial */}
      <EditorialSection
        eyebrow="NOTRE PHILOSOPHIE"
        title="MINIMALISME ASSUMÉ"
        text="Chez SIÈCLE, chaque pièce est pensée pour durer au-delà des saisons. Pas de surcharge, pas d'ostentation. Juste la justesse."
        btnLabel="EN SAVOIR PLUS"
        btnLink="/boutique"
      >
        <div style={{
          background: 'linear-gradient(135deg, #111 0%, #1a1a1a 100%)',
          aspectRatio: '4/5',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 80, fontWeight: 900, color: 'rgba(255,255,255,0.04)',
          }}>
            S
          </span>
        </div>
      </EditorialSection>

      {/* Featured products */}
      {featured.length > 0 && (
        <section style={{ padding: '80px 24px' }}>
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 48 }}>
              <div>
                <p style={{ color: 'var(--siecle-beige)', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 10 }}>
                  SÉLECTION
                </p>
                <h2 style={{
                  fontFamily: 'Montserrat, sans-serif',
                  fontSize: 'clamp(22px, 3vw, 36px)', fontWeight: 900, color: '#fff',
                }}>
                  PIÈCES DU MOMENT
                </h2>
              </div>
              <Link to="/boutique" style={{ fontSize: 11, fontWeight: 700, color: 'rgba(255,255,255,0.4)', letterSpacing: '0.15em' }}>
                VOIR TOUT →
              </Link>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }} className="featured-grid">
              {featured.map(p => <ProductCard key={p.id} product={p} />)}
            </div>
          </div>
        </section>
      )}

      {/* CTA loyalty */}
      <section style={{ padding: '80px 24px', textAlign: 'center' }}>
        <div style={{ maxWidth: 600, margin: '0 auto' }}>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <p style={{ color: 'var(--siecle-beige)', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 16 }}>
              PROGRAMME SIÈCLE
            </p>
            <h2 style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(24px, 3.5vw, 42px)', fontWeight: 900, color: '#fff', marginBottom: 18,
            }}>
              REJOIGNEZ LE CERCLE
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, lineHeight: 1.8, marginBottom: 36 }}>
              Gagnez des points à chaque achat. Accédez à des récompenses exclusives,
              des ventes privées et des avantages réservés aux membres.
            </p>
            <Link to="/compte/inscription" style={{
              display: 'inline-block', padding: '14px 36px',
              background: 'var(--siecle-beige)', color: '#000',
              fontSize: 11, fontWeight: 800, letterSpacing: '0.16em',
            }}>
              CRÉER UN COMPTE
            </Link>
          </motion.div>
        </div>
      </section>

      <style>{`
        @media (max-width: 900px) { .universe-grid { grid-template-columns: 1fr !important; } }
        @media (max-width: 768px) { .featured-grid { grid-template-columns: repeat(2, 1fr) !important; } }
      `}</style>
    </div>
  )
}
