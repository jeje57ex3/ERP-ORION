import { useState } from 'react'
import { motion } from 'framer-motion'
import PageTransition from '../components/PageTransition'
import { useCart } from '../hooks/useCart'
import { staggerContainer, fadeUp } from '../utils/animations'

const PACKS = [
  { id: 'pack-signature', name: 'Pack Signature', description: 'L\'essentiel SIÈCLE : hoodie, montre et rouge à lèvres signature.', items: ['Hoodie SIÈCLE Noir', 'Montre Urban Noire', 'Rouge à Lèvres Nude'], price: 189, normalPrice: 249, points: 250, accent: '#D8C7A3', badge: 'BEST-SELLER' },
  { id: 'pack-nuit',      name: 'Pack Nuit',      description: 'Pour les soirées urbaines : cargo premium, montre acier, palette smoky.', items: ['Pantalon Cargo SIÈCLE', 'Montre SIÈCLE Acier', 'Palette Smoky Eyes'], price: 219, normalPrice: 289, points: 300, accent: '#c9a45c', badge: 'ÉDITION LIMITÉE' },
  { id: 'pack-minimal',   name: 'Pack Minimal',   description: 'L\'élégance dans la simplicité. T-shirt blanc, bracelet cuir, fond de teint.', items: ['T-shirt Blanc Premium', 'Bracelet Cuir Naturel', 'Fond de Teint Fluide'], price: 129, normalPrice: 169, points: 180, accent: '#e8e8e8', badge: '' },
  { id: 'pack-elegance',  name: 'Pack Élégance',  description: 'Raffinement et douceur pour toutes les occasions.', items: ['Veste Premium SIÈCLE', 'Montre Dorée', 'Palette Nude'], price: 259, normalPrice: 349, points: 350, accent: '#c9a45c', badge: 'NOUVEAU' },
  { id: 'pack-full',      name: 'Pack Full SIÈCLE', description: 'L\'expérience complète. Tout l\'univers SIÈCLE en un seul coffret.', items: ['Hoodie + Cargo SIÈCLE', 'Montre Personnalisée', 'Routine Maquillage', 'Carte Cadeau 50€'], price: 449, normalPrice: 619, points: 600, accent: '#D8C7A3', badge: 'BEST VALUE' },
]

export default function PremiumPacks() {
  const { addItem } = useCart()
  const [added, setAdded] = useState(null)

  const handleAdd = (pack) => {
    addItem?.({ id: pack.id, name: pack.name, price: pack.price, quantity: 1, type: 'pack' })
    setAdded(pack.id)
    setTimeout(() => setAdded(null), 2000)
  }

  return (
    <PageTransition>
      <div style={{ minHeight: '100vh', background: '#000', paddingTop: 120, paddingBottom: 100 }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 24px' }}>
          <motion.div initial="hidden" animate="visible" variants={staggerContainer} style={{ textAlign: 'center', marginBottom: 72 }}>
            <motion.div variants={fadeUp} style={{ fontSize: 11, letterSpacing: '0.3em', color: 'var(--siecle-beige)', marginBottom: 16 }}>COLLECTIONS EXCLUSIVES</motion.div>
            <motion.h1 variants={fadeUp} style={{ fontSize: 'clamp(36px,6vw,64px)', fontWeight: 900, letterSpacing: '0.06em', color: '#fff', marginBottom: 16 }}>PACKS PREMIUM</motion.h1>
            <motion.p variants={fadeUp} style={{ color: '#666', fontSize: 15, maxWidth: 480, margin: '0 auto' }}>Des associations pensées pour sublimer votre style. Économisez jusqu'à 30% et gagnez des points bonus.</motion.p>
          </motion.div>

          <motion.div initial="hidden" animate="visible" variants={staggerContainer}
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 28 }}>
            {PACKS.map(pack => (
              <motion.div key={pack.id} variants={fadeUp}
                style={{ background: '#0d0d0d', border: `1px solid rgba(255,255,255,0.08)`, borderRadius: 20, overflow: 'hidden', transition: 'all 0.3s', position: 'relative' }}
                whileHover={{ y: -6, borderColor: `${pack.accent}40` }}>
                {pack.badge && (
                  <div style={{ position: 'absolute', top: 16, right: 16, background: pack.accent, color: '#000', fontSize: 9, fontWeight: 900, letterSpacing: '0.16em', padding: '4px 10px', borderRadius: 4 }}>{pack.badge}</div>
                )}
                <div style={{ height: 180, background: `linear-gradient(135deg, rgba(${pack.accent === '#D8C7A3' ? '216,199,163' : '201,164,92'},0.08), transparent)`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{ fontSize: 48, fontWeight: 900, letterSpacing: '0.12em', color: pack.accent, opacity: 0.15 }}>SIÈCLE</div>
                </div>
                <div style={{ padding: 28 }}>
                  <h3 style={{ fontSize: 20, fontWeight: 900, letterSpacing: '0.08em', color: '#fff', marginBottom: 10 }}>{pack.name}</h3>
                  <p style={{ color: '#888', fontSize: 13, lineHeight: 1.6, marginBottom: 20 }}>{pack.description}</p>
                  <ul style={{ listStyle: 'none', padding: 0, marginBottom: 24 }}>
                    {pack.items.map(item => (
                      <li key={item} style={{ fontSize: 12, color: '#aaa', padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ color: pack.accent, fontSize: 10 }}>✓</span> {item}
                      </li>
                    ))}
                  </ul>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 20 }}>
                    <div>
                      <span style={{ fontSize: 26, fontWeight: 900, color: '#fff' }}>{pack.price} €</span>
                      <span style={{ fontSize: 13, color: '#555', textDecoration: 'line-through', marginLeft: 8 }}>{pack.normalPrice} €</span>
                    </div>
                    <span style={{ fontSize: 11, color: pack.accent }}>+{pack.points} pts</span>
                  </div>
                  <button onClick={() => handleAdd(pack)}
                    style={{ width: '100%', padding: '14px 20px', background: added === pack.id ? '#22c55e' : '#fff', color: added === pack.id ? '#fff' : '#000', border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer', transition: 'all 0.3s' }}>
                    {added === pack.id ? '✓ AJOUTÉ' : 'AJOUTER AU PANIER'}
                  </button>
                </div>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </div>
    </PageTransition>
  )
}
