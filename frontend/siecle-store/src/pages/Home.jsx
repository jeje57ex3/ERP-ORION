import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import MotionPage, { fadeUp } from '../components/MotionPage'
import CollectionCard from '../components/CollectionCard'
import ProductGrid from '../components/ProductGrid'
import Loader from '../components/Loader'
import { getProducts, getCollections } from '../api/products'

export default function Home() {
  const [products,    setProducts]    = useState([])
  const [collections, setCollections] = useState([])
  const [loading,     setLoading]     = useState(true)

  useEffect(() => {
    Promise.all([
      getProducts({ popular: true, limit: 8 }),
      getCollections(),
    ])
      .then(([p, c]) => {
        setProducts(p.results ?? p)
        setCollections(c.results ?? c)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Loader />

  return (
    <MotionPage>
      {/* HERO */}
      <section style={{
        position: 'relative', height: '100vh', minHeight: 600,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        overflow: 'hidden',
        background: 'linear-gradient(160deg, #0A0A0A 0%, #1A1510 60%, #0A0A0A 100%)',
      }}>
        {/* Decorative line */}
        <div style={{
          position: 'absolute', top: 0, left: '50%',
          width: 1, height: '40%',
          background: 'linear-gradient(to bottom, transparent, rgba(216,199,163,0.3))',
        }} />

        <div style={{ textAlign: 'center', padding: '0 24px', zIndex: 1 }}>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0, transition: { delay: 0.2 } }}
            style={{
              color: 'var(--siecle-beige)', fontSize: 11,
              fontWeight: 800, letterSpacing: '0.3em', marginBottom: 24,
            }}
          >
            NOUVELLE COLLECTION
          </motion.p>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0, transition: { delay: 0.35, duration: 0.7 } }}
            style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(52px, 9vw, 120px)',
              fontWeight: 900, lineHeight: 0.9,
              letterSpacing: '-0.02em', color: '#fff',
              marginBottom: 32,
            }}
          >
            SIÈCLE
          </motion.h1>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { delay: 0.6 } }}
            style={{ color: 'var(--siecle-muted)', fontSize: 16, lineHeight: 1.7, maxWidth: 400, margin: '0 auto 40px' }}
          >
            Luxe contemporain. Éditions limitées.<br />Chaque pièce raconte un siècle.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0, transition: { delay: 0.8 } }}
            style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}
          >
            <Link to="/shop" style={{
              padding: '14px 36px', background: 'var(--siecle-beige)', color: '#000',
              fontSize: 12, fontWeight: 800, letterSpacing: '0.14em',
            }}>
              DÉCOUVRIR
            </Link>
            <Link to="/shop?category=montres" style={{
              padding: '14px 36px', border: '1px solid rgba(255,255,255,0.2)', color: '#fff',
              fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', background: 'transparent',
            }}>
              MONTRES
            </Link>
          </motion.div>
        </div>

        {/* Scroll cue */}
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ repeat: Infinity, duration: 1.8 }}
          style={{
            position: 'absolute', bottom: 32, left: '50%', transform: 'translateX(-50%)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
          }}
        >
          <span style={{ fontSize: 10, letterSpacing: '0.2em', color: 'var(--siecle-muted)' }}>SCROLL</span>
          <div style={{ width: 1, height: 40, background: 'linear-gradient(to bottom, rgba(255,255,255,0.2), transparent)' }} />
        </motion.div>
      </section>

      {/* COLLECTIONS */}
      {collections.length > 0 && (
        <section style={{ padding: '96px 24px', maxWidth: 1440, margin: '0 auto' }}>
          <motion.div
            variants={fadeUp} initial="hidden" whileInView="visible"
            viewport={{ once: true }}
            style={{ textAlign: 'center', marginBottom: 56 }}
          >
            <p style={{ color: 'var(--siecle-beige)', fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', marginBottom: 12 }}>
              NOS UNIVERS
            </p>
            <h2 style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(28px, 4vw, 48px)', fontWeight: 900,
              letterSpacing: '0.04em', color: '#fff',
            }}>
              COLLECTIONS
            </h2>
          </motion.div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 20,
          }}>
            {collections.map((col, i) => (
              <CollectionCard key={col.id || col.slug} collection={col} index={i} />
            ))}
          </div>
        </section>
      )}

      {/* POPULAR PRODUCTS */}
      {products.length > 0 && (
        <section style={{ padding: '0 24px 96px', maxWidth: 1440, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 48, flexWrap: 'wrap', gap: 16 }}>
            <motion.div variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}>
              <p style={{ color: 'var(--siecle-beige)', fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', marginBottom: 8 }}>
                LES FAVORIS
              </p>
              <h2 style={{
                fontFamily: 'Montserrat, sans-serif',
                fontSize: 'clamp(24px, 3.5vw, 40px)', fontWeight: 900,
                letterSpacing: '0.04em', color: '#fff',
              }}>
                POPULAIRES
              </h2>
            </motion.div>
            <Link to="/shop" style={{
              fontSize: 11, fontWeight: 800, letterSpacing: '0.12em',
              color: 'var(--siecle-beige)', borderBottom: '1px solid var(--siecle-beige)',
              paddingBottom: 2,
            }}>
              VOIR TOUT →
            </Link>
          </div>

          <ProductGrid products={products.slice(0, 8)} columns={4} />
        </section>
      )}

      {/* STORYTELLING */}
      <section style={{
        background: '#0A0A0A', borderTop: '1px solid rgba(255,255,255,0.04)',
        borderBottom: '1px solid rgba(255,255,255,0.04)',
        padding: '96px 24px',
      }}>
        <div style={{
          maxWidth: 1200, margin: '0 auto',
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 80, alignItems: 'center',
        }}
          className="siecle-story-grid"
        >
          <motion.div
            variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}
          >
            <p style={{ color: 'var(--siecle-beige)', fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', marginBottom: 16 }}>
              NOTRE PHILOSOPHIE
            </p>
            <h2 style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(28px, 3.5vw, 44px)', fontWeight: 900,
              letterSpacing: '0.02em', color: '#fff',
              lineHeight: 1.1, marginBottom: 24,
            }}>
              UN SIÈCLE<br />DE STYLE
            </h2>
            <p style={{ color: 'var(--siecle-muted)', fontSize: 15, lineHeight: 1.8, marginBottom: 20 }}>
              Chaque collection SIÈCLE est une ode à l'intemporel. Nous créons des pièces
              pensées pour durer, loin des tendances éphémères.
            </p>
            <p style={{ color: 'var(--siecle-muted)', fontSize: 15, lineHeight: 1.8, marginBottom: 36 }}>
              De la première esquisse à la pièce finale, chaque étape est maîtrisée pour
              vous offrir l'excellence que vous méritez.
            </p>
            <Link to="/shop" style={{
              padding: '14px 32px', background: 'transparent',
              border: '1px solid var(--siecle-beige)', color: 'var(--siecle-beige)',
              fontSize: 11, fontWeight: 800, letterSpacing: '0.14em', display: 'inline-block',
            }}>
              EXPLORER LA BOUTIQUE
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            style={{
              aspectRatio: '3/4',
              background: 'linear-gradient(135deg, #1A1510 0%, #2D241C 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <span style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 96, fontWeight: 900, letterSpacing: '0.05em',
              color: 'rgba(216,199,163,0.08)',
            }}>S</span>
          </motion.div>
        </div>
        <style>{`
          @media (max-width: 768px) {
            .siecle-story-grid { grid-template-columns: 1fr !important; gap: 40px !important; }
          }
        `}</style>
      </section>

      {/* NEWSLETTER */}
      <section style={{ padding: '80px 24px', textAlign: 'center' }}>
        <motion.div
          variants={fadeUp} initial="hidden" whileInView="visible" viewport={{ once: true }}
          style={{ maxWidth: 480, margin: '0 auto' }}
        >
          <p style={{ color: 'var(--siecle-beige)', fontSize: 10, fontWeight: 800, letterSpacing: '0.2em', marginBottom: 12 }}>
            ACCÈS PRIORITAIRE
          </p>
          <h3 style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 'clamp(22px, 3vw, 32px)', fontWeight: 900,
            color: '#fff', marginBottom: 16, letterSpacing: '0.04em',
          }}>
            REJOIGNEZ LE CERCLE
          </h3>
          <p style={{ color: 'var(--siecle-muted)', fontSize: 14, marginBottom: 28, lineHeight: 1.7 }}>
            Nouveautés, éditions limitées et offres exclusives en avant-première.
          </p>
          <form style={{ display: 'flex', gap: 0 }}
            onSubmit={e => e.preventDefault()}
          >
            <input
              type="email" placeholder="Votre adresse e-mail"
              style={{
                flex: 1, padding: '14px 16px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)',
                borderRight: 'none',
                color: '#fff', fontSize: 13,
                outline: 'none',
              }}
            />
            <button type="submit" style={{
              padding: '14px 24px',
              background: 'var(--siecle-beige)', color: '#000',
              border: 'none', cursor: 'pointer',
              fontSize: 11, fontWeight: 800, letterSpacing: '0.12em',
              whiteSpace: 'nowrap',
            }}>
              S'INSCRIRE
            </button>
          </form>
        </motion.div>
      </section>
    </MotionPage>
  )
}
