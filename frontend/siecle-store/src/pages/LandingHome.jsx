import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import PremiumHero from '../components/PremiumHero'
import BrandTicker from '../components/BrandTicker'
import ManifestoStatement from '../components/ManifestoStatement'
import WorldCard from '../components/WorldCard'
import EditorialSection from '../components/EditorialSection'
import ProductGrid from '../components/ProductGrid'
import TrustBand from '../components/TrustBand'
import NewsletterSection from '../components/NewsletterSection'
import InstagramCommunity from '../components/InstagramCommunity'
import { getProducts } from '../api/products'

const DISCIPLINES = [
  {
    number: '01',
    subtitle: 'STREETWEAR — PIÈCES DU QUOTIDIEN',
    title: 'Vestiaire Urbain',
    link: '/vetements',
  },
  {
    number: '02',
    subtitle: 'SUR-MESURE — SAVOIR-FAIRE ITALIEN',
    title: 'Tailleur Italien',
    link: '/vetements?categorie=tailleur',
  },
]

export default function LandingHome() {
  const [featured, setFeatured] = useState([])

  useEffect(() => {
    getProducts({ featured: true, limit: 4 }).then(d => setFeatured(d.results.slice(0, 4))).catch(() => {})
  }, [])

  return (
    <div style={{ background: 'var(--siecle-black)' }}>
      {/* Hero */}
      <PremiumHero
        topline="SIÈCLE / CHAPITRE 001 · PARIS · EUROPE · MMXXVI"
        slogan="VESTIAIRE URBAIN · TAILLEUR ITALIEN"
        title="SIÈCLE"
        subtitle="Des collections pensées pour celles et ceux qui ne cherchent pas à en faire trop — juste à bien le faire."
        primaryBtn="VOIR LE DROP"
        primaryLink="/boutique"
        secondaryBtn="DÉCOUVRIR LE TAILLEUR"
        secondaryLink="/vetements?categorie=tailleur"
        leftLabel="MAISON INDÉPENDANTE"
        rightLabel="OMBRE · COUPE · MATIÈRE"
      />

      {/* Ticker */}
      <BrandTicker />

      {/* 01 / Le manifeste */}
      <ManifestoStatement />

      {/* 02 / Les disciplines */}
      <section style={{ padding: '100px 24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <p style={{ color: 'var(--siecle-muted)', fontSize: 10, fontWeight: 600, letterSpacing: '0.2em', marginBottom: 12, textAlign: 'center' }}>
            02 / LES DISCIPLINES
          </p>
          <h2 style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(26px, 4vw, 48px)', fontWeight: 700, color: 'var(--siecle-white)',
            textAlign: 'center', marginBottom: 56,
          }}>
            DEUX SAVOIR-FAIRE, UNE SIGNATURE
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 20 }} className="disciplines-grid">
            {DISCIPLINES.map((d, i) => (
              <WorldCard key={d.title} {...d} index={i} />
            ))}
          </div>
        </div>
      </section>

      {/* 03 / En circulation */}
      {featured.length > 0 && (
        <section style={{ padding: '80px 24px' }}>
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 48 }}>
              <div>
                <p style={{ color: 'var(--siecle-muted)', fontSize: 10, fontWeight: 600, letterSpacing: '0.2em', marginBottom: 10 }}>
                  03 / EN CIRCULATION
                </p>
                <h2 style={{
                  fontFamily: 'var(--font-heading)',
                  fontSize: 'clamp(22px, 3vw, 36px)', fontWeight: 700, color: 'var(--siecle-white)',
                }}>
                  PIÈCES DU MOMENT
                </h2>
              </div>
              <Link to="/boutique" style={{ fontSize: 11, fontWeight: 700, color: 'var(--siecle-muted)', letterSpacing: '0.15em' }}>
                VOIR TOUT →
              </Link>
            </div>
            <ProductGrid products={featured} columns={4} />
          </div>
        </section>
      )}

      {/* 04 / L'intention */}
      <EditorialSection
        index="04 / L'INTENTION"
        eyebrow="NOTRE PHILOSOPHIE"
        title="MINIMALISME ASSUMÉ"
        quote="Le silence est un langage. La coupe, une signature."
        text="Chez SIÈCLE, chaque pièce est pensée pour durer au-delà des saisons. Pas de surcharge, pas d'ostentation. Juste la justesse."
        btnLabel="EN SAVOIR PLUS"
        btnLink="/boutique"
      >
        <div style={{
          background: 'linear-gradient(135deg, var(--siecle-dark) 0%, var(--siecle-dark-soft) 100%)',
          aspectRatio: '4/5',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 80, fontWeight: 700, color: 'var(--siecle-border)',
          }}>
            S
          </span>
        </div>
      </EditorialSection>

      {/* Services */}
      <TrustBand />

      {/* Newsletter / communauté (pas d'équivalent dans le thème de référence, conservés) */}
      <NewsletterSection />
      <InstagramCommunity />

      {/* CTA fidélité */}
      <section style={{ padding: '80px 24px', textAlign: 'center' }}>
        <div style={{ maxWidth: 600, margin: '0 auto' }}>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <p style={{ color: 'var(--siecle-beige)', fontSize: 9, fontWeight: 700, letterSpacing: '0.28em', marginBottom: 16 }}>
              PROGRAMME SIÈCLE
            </p>
            <h2 style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 'clamp(24px, 3.5vw, 42px)', fontWeight: 700, color: 'var(--siecle-white)', marginBottom: 18,
            }}>
              REJOIGNEZ LE CERCLE
            </h2>
            <p style={{ color: 'var(--siecle-muted)', fontSize: 14, lineHeight: 1.8, marginBottom: 36 }}>
              Gagnez des points à chaque achat. Accédez à des récompenses exclusives,
              des ventes privées et des avantages réservés aux membres.
            </p>
            <Link to="/compte/inscription" style={{
              display: 'inline-block', padding: '14px 36px',
              background: 'var(--siecle-beige)', color: 'var(--siecle-black)',
              fontSize: 11, fontWeight: 700, letterSpacing: '0.16em',
            }}>
              CRÉER UN COMPTE
            </Link>
          </motion.div>
        </div>
      </section>

      <style>{`
        @media (max-width: 768px) { .disciplines-grid { grid-template-columns: 1fr !important; } }
      `}</style>
    </div>
  )
}
