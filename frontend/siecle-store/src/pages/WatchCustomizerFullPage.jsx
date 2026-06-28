import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import Watch3DCustomizer from '../components/Watch3DCustomizer'
import '../styles/watch-customizer.css'

const DEMO_PRODUCT = {
  id: 'custom',
  name: 'SIÈCLE Atelier',
  slug: 'siecle-atelier-custom',
}

const DEMO_BASE_PRICE = 890

export default function WatchCustomizerFullPage() {
  useEffect(() => {
    document.title = 'Personnalisez votre montre — SIÈCLE Atelier'
    return () => { document.title = 'SIÈCLE' }
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: '#000', color: '#fff', paddingTop: 64 }}>
      {/* Header bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '20px 32px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        background: '#0a0a0a',
      }}>
        <div>
          <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.24em', color: '#D8C7A3', textTransform: 'uppercase', marginBottom: 4 }}>
            Configurateur exclusif
          </p>
          <h1 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 22, fontWeight: 900, letterSpacing: '0.08em', color: '#fff' }}>
            SIÈCLE ATELIER
          </h1>
        </div>
        <Link
          to="/montres"
          style={{
            fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase',
            color: '#B8B8B8', textDecoration: 'none', border: '1px solid rgba(255,255,255,0.15)',
            padding: '8px 18px', transition: 'all 0.2s',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = '#D8C7A3'; e.currentTarget.style.color = '#D8C7A3' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)'; e.currentTarget.style.color = '#B8B8B8' }}
        >
          ← Montres
        </Link>
      </div>

      {/* Intro */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        style={{ textAlign: 'center', padding: '40px 24px 0' }}
      >
        <p style={{ fontSize: 14, color: '#B8B8B8', maxWidth: 560, margin: '0 auto' }}>
          Composez votre montre pièce par pièce — boîtier, cadran, aiguilles, bracelet, couronne.
          Chaque choix se reflète immédiatement dans l'aperçu 3D.
        </p>
      </motion.div>

      {/* Customizer */}
      <Watch3DCustomizer
        product={DEMO_PRODUCT}
        basePrice={DEMO_BASE_PRICE}
        modelUrl={null}
        fallbackImage="/static/siecle/img/watch-placeholder.jpg"
      />

      {/* Bottom note */}
      <div style={{
        textAlign: 'center', padding: '40px 24px',
        borderTop: '1px solid rgba(255,255,255,0.06)',
        color: '#B8B8B8', fontSize: 13,
      }}>
        <p>Chaque montre SIÈCLE Atelier est assemblée à la main. Délai de fabrication : 4 à 6 semaines.</p>
        <p style={{ marginTop: 8, fontSize: 11, color: '#666' }}>
          Vous recevrez un email de confirmation avec un lien de suivi personnalisé.
        </p>
      </div>
    </div>
  )
}
