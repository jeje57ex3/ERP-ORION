import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import PageTransition from '../components/PageTransition'

const SIZE_TABLE = {
  XS:  { chest: '80-84', waist: '62-66', hips: '86-90', height: '155-165' },
  S:   { chest: '84-88', waist: '66-70', hips: '90-94', height: '160-170' },
  M:   { chest: '88-92', waist: '70-74', hips: '94-98', height: '165-175' },
  L:   { chest: '92-96', waist: '74-78', hips: '98-102', height: '170-180' },
  XL:  { chest: '96-100', waist: '78-82', hips: '102-106', height: '175-185' },
  XXL: { chest: '100-104', waist: '82-86', hips: '106-110', height: '175-185' },
  '3XL': { chest: '104-108', waist: '86-90', hips: '110-114', height: '175-185' },
  '4XL': { chest: '108-112', waist: '90-94', hips: '114-118', height: '175-185' },
}
const FITS = [
  { id: 'ajuste',  label: 'Ajusté',   icon: '↔', desc: 'Suit la silhouette' },
  { id: 'normal',  label: 'Normal',   icon: '▭', desc: 'Coupe droite standard' },
  { id: 'oversize',label: 'Oversize', icon: '◻', desc: 'Large et décontracté' },
]

const recommend = ({ height, chest, fit }) => {
  for (const [size, data] of Object.entries(SIZE_TABLE)) {
    const [lo, hi] = data.chest.split('-').map(Number)
    if (chest >= lo && chest <= hi) {
      if (fit === 'ajuste') return { size, note: null }
      if (fit === 'oversize') {
        const sizes = Object.keys(SIZE_TABLE)
        return { size: sizes[Math.min(sizes.indexOf(size) + 1, sizes.length - 1)], note: 'Taille supérieure pour un effet oversize prononcé' }
      }
      return { size, note: null }
    }
  }
  return { size: 'M', note: null }
}

export default function SizeGuide() {
  const [form, setForm] = useState({ height: '', weight: '', chest: '', waist: '', hips: '', fit: 'normal' })
  const [result, setResult] = useState(null)

  const update = (k, v) => setForm(f => ({ ...f, [k]: v }))
  const calc = () => {
    if (!form.chest) return
    setResult(recommend({ height: Number(form.height), chest: Number(form.chest), fit: form.fit }))
  }

  return (
    <PageTransition>
      <div style={{ minHeight: '100vh', background: '#000', paddingTop: 120, paddingBottom: 100 }}>
        <div style={{ maxWidth: 900, margin: '0 auto', padding: '0 24px' }}>
          <div style={{ marginBottom: 60 }}>
            <div style={{ fontSize: 11, letterSpacing: '0.3em', color: 'var(--siecle-beige)', marginBottom: 16 }}>VÊTEMENTS SIÈCLE</div>
            <h1 style={{ fontSize: 'clamp(32px,5vw,56px)', fontWeight: 900, color: '#fff', letterSpacing: '0.06em', marginBottom: 12 }}>GUIDE TAILLE</h1>
            <p style={{ color: '#666', fontSize: 15 }}>Trouvez votre taille parfaite pour toutes les coupes SIÈCLE.</p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 48 }}>
            {/* Formulaire */}
            <div style={{ background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, padding: 32 }}>
              <h3 style={{ fontSize: 14, fontWeight: 800, letterSpacing: '0.18em', color: 'var(--siecle-beige)', marginBottom: 28 }}>VOS MESURES</h3>
              {[
                { key: 'height', label: 'Taille (cm)', ph: '175' },
                { key: 'chest',  label: 'Tour de poitrine (cm) *', ph: '90' },
                { key: 'waist',  label: 'Tour de taille (cm)',  ph: '74' },
                { key: 'hips',   label: 'Tour de hanches (cm)', ph: '98' },
              ].map(({ key, label, ph }) => (
                <div key={key} style={{ marginBottom: 18 }}>
                  <label style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', color: '#666', display: 'block', marginBottom: 8, textTransform: 'uppercase' }}>{label}</label>
                  <input type="number" value={form[key]} onChange={e => update(key, e.target.value)} placeholder={ph}
                    style={{ width: '100%', background: '#1a1a1a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, padding: '12px 16px', color: '#fff', fontSize: 14, outline: 'none' }} />
                </div>
              ))}

              <div style={{ marginBottom: 28 }}>
                <label style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', color: '#666', display: 'block', marginBottom: 12, textTransform: 'uppercase' }}>Préférence de coupe</label>
                <div style={{ display: 'flex', gap: 10 }}>
                  {FITS.map(f => (
                    <button key={f.id} onClick={() => update('fit', f.id)}
                      style={{ flex: 1, padding: '12px 10px', background: form.fit === f.id ? '#fff' : '#1a1a1a', color: form.fit === f.id ? '#000' : '#aaa', border: `1px solid ${form.fit === f.id ? '#fff' : 'rgba(255,255,255,0.1)'}`, borderRadius: 8, cursor: 'pointer', fontSize: 11, fontWeight: 700, transition: 'all 0.2s' }}>
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>

              <button onClick={calc}
                style={{ width: '100%', padding: '14px 20px', background: '#fff', color: '#000', border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer' }}>
                CALCULER MA TAILLE
              </button>

              <AnimatePresence>
                {result && (
                  <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} style={{ marginTop: 24, textAlign: 'center', padding: 24, background: 'rgba(216,199,163,0.08)', border: '1px solid rgba(216,199,163,0.2)', borderRadius: 12 }}>
                    <div style={{ fontSize: 11, color: 'var(--siecle-beige)', letterSpacing: '0.2em', marginBottom: 8 }}>VOTRE TAILLE</div>
                    <div style={{ fontSize: 56, fontWeight: 900, color: '#fff' }}>{result.size}</div>
                    {result.note && <div style={{ fontSize: 12, color: '#888', marginTop: 8 }}>{result.note}</div>}
                    <div style={{ fontSize: 12, color: '#555', marginTop: 12 }}>Pour la coupe {form.fit}</div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Tableau */}
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 800, letterSpacing: '0.18em', color: 'var(--siecle-beige)', marginBottom: 24 }}>TABLEAU DES TAILLES</h3>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, fontSize: 13 }}>
                  <thead>
                    <tr>
                      {['Taille', 'Poitrine', 'Taille', 'Hanches', 'Hauteur'].map(h => (
                        <th key={h} style={{ padding: '10px 12px', background: '#111', color: '#888', fontSize: 10, letterSpacing: '0.14em', fontWeight: 700, textAlign: 'center', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(SIZE_TABLE).map(([size, data], i) => (
                      <tr key={size} style={{ background: result?.size === size ? 'rgba(216,199,163,0.1)' : i % 2 === 0 ? '#0d0d0d' : '#111' }}>
                        <td style={{ padding: '10px 12px', color: result?.size === size ? 'var(--siecle-beige)' : '#fff', fontWeight: 800, textAlign: 'center' }}>{size}</td>
                        <td style={{ padding: '10px 12px', color: '#aaa', textAlign: 'center' }}>{data.chest}</td>
                        <td style={{ padding: '10px 12px', color: '#aaa', textAlign: 'center' }}>{data.waist}</td>
                        <td style={{ padding: '10px 12px', color: '#aaa', textAlign: 'center' }}>{data.hips}</td>
                        <td style={{ padding: '10px 12px', color: '#aaa', textAlign: 'center' }}>{data.height}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p style={{ color: '#555', fontSize: 12, marginTop: 16 }}>Toutes les mesures sont en centimètres.</p>
            </div>
          </div>
        </div>
      </div>
    </PageTransition>
  )
}
