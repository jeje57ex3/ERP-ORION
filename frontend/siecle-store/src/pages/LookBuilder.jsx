import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import PageTransition from '../components/PageTransition'
import { useCart } from '../hooks/useCart'
import { getProducts } from '../api/products'
import { calculatePointsForProduct } from '../utils/loyaltyPoints'
import { fadeUp, staggerContainer } from '../utils/animations'

const CATEGORIES = [
  { key: 'vetements', label: 'Vêtement', icon: '👕' },
  { key: 'montres',   label: 'Montre',   icon: '⌚' },
  { key: 'maquillage',label: 'Maquillage',icon: '💄' },
]

export default function LookBuilder() {
  const { addItem } = useCart()
  const [products, setProducts] = useState({ vetements: [], montres: [], maquillage: [] })
  const [selected, setSelected] = useState({ vetements: null, montres: null, maquillage: null })
  const [added, setAdded] = useState(false)

  useEffect(() => {
    CATEGORIES.forEach(({ key }) => {
      getProducts({ category: key, limit: 6 }).then(d => setProducts(p => ({ ...p, [key]: d.results || [] }))).catch(() => {})
    })
  }, [])

  const total     = Object.values(selected).reduce((s, p) => s + (p?.price || 0), 0)
  const totalPts  = Object.values(selected).reduce((s, p) => s + calculatePointsForProduct(p?.price || 0), 0)
  const lookReady = Object.values(selected).some(Boolean)

  const handleAddLook = () => {
    Object.values(selected).filter(Boolean).forEach(p => addItem?.({ ...p, quantity: 1 }))
    setAdded(true)
    setTimeout(() => setAdded(false), 2200)
  }

  return (
    <PageTransition>
      <div style={{ minHeight: '100vh', background: '#000', paddingTop: 120, paddingBottom: 100 }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
          <motion.div initial="hidden" animate="visible" variants={staggerContainer} style={{ marginBottom: 60 }}>
            <motion.div variants={fadeUp} style={{ fontSize: 11, letterSpacing: '0.3em', color: 'var(--siecle-beige)', marginBottom: 16 }}>LOOK COMPLET</motion.div>
            <motion.h1 variants={fadeUp} style={{ fontSize: 'clamp(36px,6vw,60px)', fontWeight: 900, color: '#fff', letterSpacing: '0.06em', marginBottom: 12 }}>CRÉER MON LOOK</motion.h1>
            <motion.p variants={fadeUp} style={{ color: '#666', fontSize: 15 }}>Composez votre look parfait en 3 univers SIÈCLE.</motion.p>
          </motion.div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 48 }}>
            <div>
              {CATEGORIES.map(({ key, label, icon }) => (
                <div key={key} style={{ marginBottom: 48 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                    <span style={{ fontSize: 20 }}>{icon}</span>
                    <h3 style={{ fontSize: 14, fontWeight: 800, letterSpacing: '0.18em', color: 'var(--siecle-beige)' }}>{label.toUpperCase()}</h3>
                    {selected[key] && <span style={{ fontSize: 11, color: '#22c55e' }}>✓ Sélectionné</span>}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 14 }}>
                    {(products[key].length ? products[key] : Array(4).fill(null)).map((p, i) => (
                      <motion.div key={p?.id || i} whileHover={{ y: -4 }} onClick={() => setSelected(s => ({ ...s, [key]: s[key]?.id === p?.id ? null : p }))}
                        style={{ background: selected[key]?.id === p?.id ? 'rgba(216,199,163,0.1)' : '#111', border: `1px solid ${selected[key]?.id === p?.id ? 'var(--siecle-beige)' : 'rgba(255,255,255,0.08)'}`, borderRadius: 12, padding: 16, cursor: 'pointer', transition: 'all 0.2s' }}>
                        <div style={{ height: 100, background: '#1a1a1a', borderRadius: 8, marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28 }}>{icon}</div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', marginBottom: 4 }}>{p?.name || '—'}</div>
                        <div style={{ fontSize: 13, color: 'var(--siecle-beige)' }}>{p?.price ? `${p.price} €` : '—'}</div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Récap look */}
            <div style={{ position: 'sticky', top: 100, height: 'fit-content', background: '#111', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, padding: 28 }}>
              <h3 style={{ fontSize: 14, fontWeight: 800, letterSpacing: '0.18em', color: 'var(--siecle-beige)', marginBottom: 24 }}>MON LOOK</h3>
              {CATEGORIES.map(({ key, label, icon }) => (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  <span>{icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: '#666', marginBottom: 2 }}>{label}</div>
                    <div style={{ fontSize: 13, color: selected[key] ? '#fff' : '#444', fontWeight: selected[key] ? 600 : 400 }}>
                      {selected[key]?.name || 'Non sélectionné'}
                    </div>
                  </div>
                  {selected[key] && <div style={{ fontSize: 13, color: 'var(--siecle-beige)' }}>{selected[key].price} €</div>}
                </div>
              ))}

              {lookReady && (
                <div style={{ marginTop: 24, paddingTop: 20, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ color: '#888', fontSize: 13 }}>Total</span>
                    <span style={{ color: '#fff', fontWeight: 900, fontSize: 18 }}>{total.toFixed(2)} €</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--siecle-beige)', textAlign: 'right', marginBottom: 20 }}>+{totalPts} points fidélité</div>
                  <button onClick={handleAddLook}
                    style={{ width: '100%', padding: '14px 20px', background: added ? '#22c55e' : '#fff', color: added ? '#fff' : '#000', border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer', transition: 'all 0.3s' }}>
                    {added ? '✓ AJOUTÉ' : 'AJOUTER LE LOOK'}
                  </button>
                </div>
              )}
              {!lookReady && <p style={{ color: '#444', fontSize: 13, textAlign: 'center', marginTop: 24 }}>Sélectionnez au moins un article</p>}
            </div>
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
