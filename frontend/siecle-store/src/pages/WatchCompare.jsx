import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import PageTransition from '../components/PageTransition'
import { getProducts } from '../api/products'
import { useCart } from '../hooks/useCart'

const SPECS = ['price', 'material', 'dial_color', 'strap', 'movement', 'diameter', 'customizable']
const SPEC_LABELS = { price: 'Prix', material: 'Boîtier', dial_color: 'Cadran', strap: 'Bracelet', movement: 'Mouvement', diameter: 'Diamètre', customizable: 'Personnalisable' }

export default function WatchCompare() {
  const [watches, setWatches] = useState([])
  const [selected, setSelected] = useState([null, null])
  const [open, setOpen] = useState(null)
  const { addItem } = useCart()

  useEffect(() => {
    getProducts({ category: 'montres', limit: 12 }).then(d => setWatches(d.results || [])).catch(() => {})
  }, [])

  const pick = (idx, watch) => {
    const next = [...selected]
    next[idx] = watch
    setSelected(next)
    setOpen(null)
  }

  const A = selected[0], B = selected[1]

  const cell = (val, other) => {
    if (val === undefined || val === null) return '—'
    if (typeof val === 'boolean') return val ? '✓' : '✗'
    return val
  }

  return (
    <PageTransition>
      <div style={{ minHeight: '100vh', background: '#000', paddingTop: 120, paddingBottom: 100 }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 24px' }}>
          <div style={{ marginBottom: 56, textAlign: 'center' }}>
            <div style={{ fontSize: 11, letterSpacing: '0.3em', color: 'var(--siecle-beige)', marginBottom: 16 }}>MONTRES SIÈCLE</div>
            <h1 style={{ fontSize: 'clamp(32px,5vw,56px)', fontWeight: 900, color: '#fff', letterSpacing: '0.06em' }}>COMPARATEUR</h1>
          </div>

          {/* Sélecteurs */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 48 }}>
            {[0, 1].map(idx => (
              <div key={idx}>
                <div style={{ background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 16, padding: 24, cursor: 'pointer', minHeight: 180, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}
                  onClick={() => setOpen(open === idx ? null : idx)}>
                  {selected[idx] ? (
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ width: 80, height: 80, background: '#1a1a1a', borderRadius: '50%', margin: '0 auto 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 36 }}>⌚</div>
                      <div style={{ fontSize: 16, fontWeight: 800, color: '#fff' }}>{selected[idx].name}</div>
                      <div style={{ fontSize: 14, color: 'var(--siecle-beige)', marginTop: 6 }}>{selected[idx].price} €</div>
                    </div>
                  ) : (
                    <div style={{ textAlign: 'center', color: '#444' }}>
                      <div style={{ fontSize: 40, marginBottom: 12 }}>+</div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>Choisir une montre</div>
                    </div>
                  )}
                </div>

                {open === idx && (
                  <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    style={{ background: '#111', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, marginTop: 8, maxHeight: 300, overflowY: 'auto' }}>
                    {watches.map(w => (
                      <div key={w.id} onClick={() => pick(idx, w)}
                        style={{ padding: '14px 18px', cursor: 'pointer', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#fff', fontSize: 14 }}>{w.name}</span>
                        <span style={{ color: 'var(--siecle-beige)', fontSize: 13 }}>{w.price} €</span>
                      </div>
                    ))}
                  </motion.div>
                )}
              </div>
            ))}
          </div>

          {/* Tableau comparatif */}
          {(A || B) && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                <thead>
                  <tr>
                    <th style={{ padding: '16px 20px', color: '#666', fontSize: 11, letterSpacing: '0.14em', textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.06)', width: '30%' }}>CRITÈRE</th>
                    <th style={{ padding: '16px 20px', color: A ? '#fff' : '#444', fontWeight: 800, textAlign: 'center', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>{A?.name || '—'}</th>
                    <th style={{ padding: '16px 20px', color: B ? '#fff' : '#444', fontWeight: 800, textAlign: 'center', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>{B?.name || '—'}</th>
                  </tr>
                </thead>
                <tbody>
                  {SPECS.map((spec, i) => (
                    <tr key={spec} style={{ background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                      <td style={{ padding: '14px 20px', color: '#888', fontSize: 12, letterSpacing: '0.1em' }}>{SPEC_LABELS[spec]}</td>
                      <td style={{ padding: '14px 20px', color: '#fff', textAlign: 'center', fontWeight: 600 }}>{cell(A?.[spec])}</td>
                      <td style={{ padding: '14px 20px', color: '#fff', textAlign: 'center', fontWeight: 600 }}>{cell(B?.[spec])}</td>
                    </tr>
                  ))}
                  <tr>
                    <td style={{ padding: '20px' }} />
                    <td style={{ padding: '20px', textAlign: 'center' }}>
                      {A && <button onClick={() => addItem?.({ ...A, quantity: 1 })} style={{ padding: '12px 24px', background: '#fff', color: '#000', border: 'none', borderRadius: 8, fontSize: 11, fontWeight: 800, cursor: 'pointer', letterSpacing: '0.12em' }}>CHOISIR</button>}
                    </td>
                    <td style={{ padding: '20px', textAlign: 'center' }}>
                      {B && <button onClick={() => addItem?.({ ...B, quantity: 1 })} style={{ padding: '12px 24px', background: '#fff', color: '#000', border: 'none', borderRadius: 8, fontSize: 11, fontWeight: 800, cursor: 'pointer', letterSpacing: '0.12em' }}>CHOISIR</button>}
                    </td>
                  </tr>
                </tbody>
              </table>
            </motion.div>
          )}
        </div>
      </div>
    </PageTransition>
  )
}
