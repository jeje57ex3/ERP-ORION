import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import PageTransition from '../components/PageTransition'
import { fadeUp } from '../utils/animations'

function Countdown({ target }) {
  const [diff, setDiff] = useState(0)

  useEffect(() => {
    const update = () => setDiff(Math.max(0, new Date(target) - Date.now()))
    update()
    const t = setInterval(update, 1000)
    return () => clearInterval(t)
  }, [target])

  const total = Math.floor(diff / 1000)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = n => String(n).padStart(2, '0')

  return (
    <div style={{ display: 'flex', gap: 24, justifyContent: 'center', marginBottom: 48 }}>
      {[{ v: h, l: 'H' }, { v: m, l: 'MIN' }, { v: s, l: 'SEC' }].map(({ v, l }) => (
        <div key={l} style={{ textAlign: 'center' }}>
          <p style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 48, fontWeight: 900, color: '#fff', margin: 0, lineHeight: 1 }}>
            {pad(v)}
          </p>
          <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.22em', color: 'rgba(255,255,255,0.3)', marginTop: 6 }}>{l}</p>
        </div>
      ))}
    </div>
  )
}

const DEMO_PRODUCTS = [
  { id: 1, name: 'Veste Signature Noire', price: '189,00 €', stock: 12 },
  { id: 2, name: 'Montre Édition Limitée', price: '249,00 €', stock: 5 },
  { id: 3, name: 'Coffret SIÈCLE Night',  price: '149,00 €', stock: 8 },
]

export default function PrivateDrop() {
  const { code } = useParams()
  const [access,   setAccess]   = useState(null) // null | 'checking' | 'granted' | 'denied'
  const [codeInput, setCode]    = useState(code || '')
  const [drop,     setDrop]     = useState(null)

  const check = () => {
    setAccess('checking')
    fetch(`/api/v1/siecle/drops/check-access/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: codeInput }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.access) { setDrop(d.drop); setAccess('granted') }
        else setAccess('denied')
      })
      .catch(() => { setDrop({ name: 'DROP NUIT', demo: true }); setAccess('granted') })
  }

  return (
    <PageTransition>
      <div style={{ minHeight: '100vh', background: '#000', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 24px' }}>

        {(!access || access === 'denied') && (
          <motion.div variants={fadeUp} initial="hidden" animate="visible" style={{ maxWidth: 480, width: '100%', textAlign: 'center' }}>
            <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.28em', color: 'var(--siecle-beige)', marginBottom: 16 }}>
              ACCÈS RÉSERVÉ
            </p>
            <h1 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(28px, 5vw, 48px)', fontWeight: 900, marginBottom: 16 }}>
              DROP PRIVÉ
            </h1>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, lineHeight: 1.7, marginBottom: 40 }}>
              Cet accès est réservé aux membres invités ou aux clients Gold & Black.
            </p>
            <input
              type="text" value={codeInput}
              onChange={e => setCode(e.target.value)}
              placeholder="Entrez votre code d'accès"
              style={{ width: '100%', height: 52, padding: '0 20px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', fontSize: 14, outline: 'none', marginBottom: 12, fontFamily: 'inherit' }}
            />
            {access === 'denied' && <p style={{ color: '#C05070', fontSize: 12, marginBottom: 12 }}>Code incorrect ou accès non autorisé.</p>}
            <button onClick={check} style={{ width: '100%', height: 52, background: 'var(--siecle-beige)', color: '#000', border: 'none', fontSize: 11, fontWeight: 800, letterSpacing: '0.16em', cursor: 'pointer' }}>
              {access === 'checking' ? 'VÉRIFICATION…' : 'ACCÉDER AU DROP'}
            </button>
          </motion.div>
        )}

        {access === 'granted' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ maxWidth: 800, width: '100%', textAlign: 'center' }}>
            <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', color: 'var(--siecle-beige)', marginBottom: 12 }}>ACCÈS ACCORDÉ</p>
            <h1 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(32px, 6vw, 60px)', fontWeight: 900, marginBottom: 40 }}>
              {drop?.name || 'DROP NUIT'}
            </h1>
            <Countdown target={new Date(Date.now() + 3 * 3600 * 1000)} />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 40 }} className="drop-grid">
              {DEMO_PRODUCTS.map(p => (
                <div key={p.id} style={{ background: '#0a0a0a', border: '1px solid rgba(255,255,255,0.08)', padding: 24 }}>
                  <div style={{ aspectRatio: '3/4', background: '#111', marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <p style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 32, fontWeight: 900, color: 'rgba(255,255,255,0.05)' }}>S</p>
                  </div>
                  <p style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>{p.name}</p>
                  <p style={{ color: 'var(--siecle-beige)', fontSize: 14, fontWeight: 700, marginBottom: 8 }}>{p.price}</p>
                  <p style={{ fontSize: 10, color: '#C05070', letterSpacing: '0.1em' }}>{p.stock} restants</p>
                  <button style={{ marginTop: 12, width: '100%', padding: '10px', background: '#fff', color: '#000', border: 'none', fontSize: 10, fontWeight: 800, letterSpacing: '0.12em', cursor: 'pointer' }}>
                    AJOUTER
                  </button>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        <style>{`@media (max-width: 640px) { .drop-grid { grid-template-columns: 1fr !important; } }`}</style>
      </div>
    </PageTransition>
  )
}
