import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../styles/makeup-home.css'

const TONES = [
  { id: 'tres-claire', label: 'Très Claire',  hex: '#FDE8D8', desc: 'Porcelaine, rose pâle' },
  { id: 'claire',      label: 'Claire',        hex: '#F5CBA7', desc: 'Ivoire, beige rosé' },
  { id: 'medium',      label: 'Medium',        hex: '#E59866', desc: 'Dorée, miel' },
  { id: 'mate',        label: 'Mate',          hex: '#CA6F1E', desc: 'Caramel, ambre' },
  { id: 'foncee',      label: 'Foncée',        hex: '#7D4700', desc: 'Châtaigne, cacao' },
  { id: 'tres-foncee', label: 'Très Foncée',  hex: '#3E1B00', desc: 'Ébène, nuit' },
]
const UNDERTONES = [
  { id: 'froid',   label: 'Froid',   icon: '❄️', desc: 'Veines bleues/violettes' },
  { id: 'neutre',  label: 'Neutre',  icon: '⚖️', desc: 'Mélange bleu et vert' },
  { id: 'chaud',   label: 'Chaud',   icon: '🔥', desc: 'Veines vertes/jaunes' },
]
const FINISHES = [
  { id: 'naturel',   label: 'Naturel',   icon: '🌿' },
  { id: 'lumineux',  label: 'Lumineux',  icon: '✨' },
  { id: 'mat',       label: 'Mat',       icon: '🪨' },
]

const RECS = {
  'tres-claire-froid':  ['FDT Porcelaine 01N', 'Correcteur Rose Pâle', 'Blush Lilas Doux'],
  'tres-claire-chaud':  ['FDT Ivoire 01W', 'Correcteur Pêche', 'Blush Pêche'],
  'claire-froid':       ['FDT Beige Rose 02N', 'Fond Teint Léger 02C', 'Blush Framboise'],
  'claire-chaud':       ['FDT Beige Doré 02W', 'Correcteur Apricot', 'Blush Corail'],
  'medium-neutre':      ['FDT Dorée 03N', 'Poudre Compact Miel', 'Blush Brique'],
  'medium-chaud':       ['FDT Caramel 03W', 'Bronzeur Ambre', 'Blush Terracotta'],
  'mate-chaud':         ['FDT Caramel Profond 04W', 'Poudre Banane', 'Blush Brun'],
  'foncee-chaud':       ['FDT Chocolat 05W', 'Correcteur Orange', 'Highlighter Cuivré'],
  'tres-foncee-chaud':  ['FDT Ébène 06W', 'Poudre Dense', 'Highlighter Bronze'],
}

export default function ShadeFinder() {
  const [tone,      setTone]      = useState(null)
  const [undertone, setUndertone] = useState(null)
  const [finish,    setFinish]    = useState(null)
  const [result,    setResult]    = useState(null)

  const find = () => {
    const key = `${tone?.id}-${undertone?.id}`
    const recs = RECS[key] || RECS['medium-neutre']
    setResult(recs)
  }

  return (
    <div className="makeup-site" style={{ minHeight: '100vh', background: 'var(--beauty-cream)', paddingBottom: 80 }}>
      <div style={{ maxWidth: 780, margin: '0 auto', padding: '80px 24px' }}>
        <div style={{ fontSize: 11, letterSpacing: '0.2em', color: 'var(--beauty-gold)', marginBottom: 16, textTransform: 'uppercase' }}>SIÈCLE BEAUTY</div>
        <h1 style={{ fontSize: 'clamp(28px,5vw,48px)', fontWeight: 700, color: 'var(--beauty-brown)', marginBottom: 8, fontFamily: 'var(--beauty-serif)' }}>Trouver ma teinte</h1>
        <p style={{ color: 'var(--beauty-muted)', marginBottom: 56 }}>Répondez à 3 questions pour trouver votre teinte parfaite.</p>

        {/* Carnation */}
        <div style={{ marginBottom: 48 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.15em', color: 'var(--beauty-brown)', marginBottom: 20, textTransform: 'uppercase' }}>Ma carnation</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
            {TONES.map(t => (
              <motion.button key={t.id} whileHover={{ scale: 1.03 }} onClick={() => setTone(t)}
                style={{ background: tone?.id === t.id ? '#fff' : 'rgba(255,255,255,0.5)', border: `2px solid ${tone?.id === t.id ? 'var(--beauty-gold)' : 'transparent'}`, borderRadius: 14, padding: '14px 12px', cursor: 'pointer', transition: 'all 0.2s' }}>
                <div style={{ width: 48, height: 48, borderRadius: '50%', background: t.hex, margin: '0 auto 10px', border: '2px solid rgba(0,0,0,0.08)' }} />
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--beauty-brown)' }}>{t.label}</div>
                <div style={{ fontSize: 11, color: 'var(--beauty-muted)' }}>{t.desc}</div>
              </motion.button>
            ))}
          </div>
        </div>

        {/* Sous-ton */}
        <div style={{ marginBottom: 48 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.15em', color: 'var(--beauty-brown)', marginBottom: 20, textTransform: 'uppercase' }}>Mon sous-ton</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
            {UNDERTONES.map(u => (
              <motion.button key={u.id} whileHover={{ scale: 1.03 }} onClick={() => setUndertone(u)}
                style={{ background: undertone?.id === u.id ? '#fff' : 'rgba(255,255,255,0.5)', border: `2px solid ${undertone?.id === u.id ? 'var(--beauty-gold)' : 'transparent'}`, borderRadius: 14, padding: '20px 14px', cursor: 'pointer', textAlign: 'center', transition: 'all 0.2s' }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>{u.icon}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--beauty-brown)' }}>{u.label}</div>
                <div style={{ fontSize: 11, color: 'var(--beauty-muted)' }}>{u.desc}</div>
              </motion.button>
            ))}
          </div>
        </div>

        {/* Rendu */}
        <div style={{ marginBottom: 48 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.15em', color: 'var(--beauty-brown)', marginBottom: 20, textTransform: 'uppercase' }}>Rendu souhaité</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
            {FINISHES.map(f => (
              <motion.button key={f.id} whileHover={{ scale: 1.03 }} onClick={() => setFinish(f)}
                style={{ background: finish?.id === f.id ? '#fff' : 'rgba(255,255,255,0.5)', border: `2px solid ${finish?.id === f.id ? 'var(--beauty-gold)' : 'transparent'}`, borderRadius: 14, padding: '20px 14px', cursor: 'pointer', textAlign: 'center', transition: 'all 0.2s' }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>{f.icon}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--beauty-brown)' }}>{f.label}</div>
              </motion.button>
            ))}
          </div>
        </div>

        <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
          onClick={find}
          disabled={!tone || !undertone}
          style={{ padding: '16px 40px', background: tone && undertone ? 'var(--beauty-brown)' : '#ccc', color: '#fff', border: 'none', borderRadius: 10, fontSize: 12, fontWeight: 800, letterSpacing: '0.16em', cursor: tone && undertone ? 'pointer' : 'not-allowed', textTransform: 'uppercase', display: 'block', width: '100%' }}>
          TROUVER MA TEINTE
        </motion.button>

        <AnimatePresence>
          {result && (
            <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} style={{ marginTop: 48, background: '#fff', border: '1px solid var(--beauty-border)', borderRadius: 20, padding: 32 }}>
              <h3 style={{ fontSize: 20, fontWeight: 700, color: 'var(--beauty-brown)', marginBottom: 8, fontFamily: 'var(--beauty-serif)' }}>Vos produits recommandés</h3>
              <p style={{ color: 'var(--beauty-muted)', fontSize: 13, marginBottom: 24 }}>Sélection basée sur votre carnation {tone?.label} · Sous-ton {undertone?.label}</p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: 12 }}>
                {result.map(p => (
                  <div key={p} style={{ background: 'var(--beauty-cream)', borderRadius: 10, padding: '16px 14px', textAlign: 'center' }}>
                    <div style={{ fontSize: 28, marginBottom: 8 }}>💄</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--beauty-brown)' }}>{p}</div>
                  </div>
                ))}
              </div>
              <a href="/shop/maquillage/" style={{ display: 'block', marginTop: 24, textAlign: 'center', padding: '14px 28px', background: 'var(--beauty-brown)', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 700, letterSpacing: '0.12em', textDecoration: 'none' }}>VOIR LA BOUTIQUE BEAUTÉ</a>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
