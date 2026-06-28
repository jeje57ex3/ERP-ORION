import { motion } from 'framer-motion'

const ICONS = { vetements: '👕', montres: '⌚', maquillage: '💄' }

export default function LookBuilderPanel({ selections, onRemove, onAddToCart }) {
  const total = Object.values(selections).reduce((s, p) => s + (p?.price || 0), 0)
  const count = Object.values(selections).filter(Boolean).length

  return (
    <div style={{ background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, padding: 24, position: 'sticky', top: 100 }}>
      <div style={{ fontSize: 12, fontWeight: 800, letterSpacing: '0.2em', color: 'var(--siecle-beige)', marginBottom: 20 }}>MON LOOK</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
        {['vetements', 'montres', 'maquillage'].map(cat => {
          const p = selections[cat]
          return (
            <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', background: p ? '#111' : '#0a0a0a', border: `1px solid ${p ? 'rgba(216,199,163,0.15)' : 'rgba(255,255,255,0.04)'}`, borderRadius: 12 }}>
              <span style={{ fontSize: 22 }}>{ICONS[cat]}</span>
              <div style={{ flex: 1 }}>
                {p ? (
                  <>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>{p.name}</div>
                    <div style={{ fontSize: 12, color: 'var(--siecle-beige)' }}>{p.price} €</div>
                  </>
                ) : (
                  <div style={{ fontSize: 12, color: '#444' }}>Aucune sélection</div>
                )}
              </div>
              {p && (
                <button onClick={() => onRemove?.(cat)} style={{ background: 'none', border: 'none', color: '#444', cursor: 'pointer', fontSize: 16, padding: 4 }}>✕</button>
              )}
            </div>
          )
        })}
      </div>

      <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <span style={{ fontSize: 12, color: '#666' }}>Total look ({count} pièce{count > 1 ? 's' : ''})</span>
          <span style={{ fontSize: 18, fontWeight: 800, color: 'var(--siecle-beige)' }}>{total} €</span>
        </div>
        <button onClick={() => onAddToCart?.(selections)} disabled={count === 0}
          style={{ width: '100%', padding: '15px', background: count > 0 ? '#fff' : '#111', color: count > 0 ? '#000' : '#333', border: 'none', borderRadius: 12, fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', cursor: count > 0 ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>
          {count === 0 ? 'SÉLECTIONNEZ DES PIÈCES' : 'AJOUTER LE LOOK AU PANIER'}
        </button>
        {count > 0 && (
          <div style={{ textAlign: 'center', marginTop: 10, fontSize: 11, color: '#555' }}>
            +{Math.round(total * 5)} points de fidélité
          </div>
        )}
      </div>
    </div>
  )
}
