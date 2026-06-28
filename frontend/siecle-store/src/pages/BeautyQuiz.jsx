import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import '../styles/makeup-home.css'

const STEPS = [
  { q: 'Quel rendu recherchez-vous ?', key: 'finish', opts: ['Naturel & no-makeup', 'Lumineux & glowy', 'Intense & soirée', 'Nude & minimaliste'] },
  { q: 'Quel est votre type de peau ?', key: 'skin', opts: ['Normale', 'Sèche', 'Grasse / mixte', 'Sensible'] },
  { q: 'Quelles teintes préférez-vous ?', key: 'tones', opts: ['Nude & beige', 'Bordeaux & prune', 'Rose & corail', 'Brun & terracotta'] },
  { q: 'Quelle texture vous convient le mieux ?', key: 'texture', opts: ['Fluide & légère', 'Mate & couvrant', 'Satinée & lumineuse', 'Crème & confort'] },
  { q: 'Quel est votre budget moyen par produit ?', key: 'budget', opts: ['Moins de 20 €', '20 € – 40 €', '40 € – 70 €', 'Sans limite'] },
]

const RESULTS = {
  'Naturel & no-makeup': { name: 'Routine Fraîcheur', products: ['Fond de teint léger SPF', 'Mascara brun', 'Gloss transparent', 'Poudre matifiante'] },
  'Lumineux & glowy':    { name: 'Routine Éclat',     products: ['Primer illuminateur', 'Fond de teint fluide', 'Highlighter doré', 'Rouge à lèvres nude'] },
  'Intense & soirée':    { name: 'Routine Nuit',       products: ['Eyeliner noir', 'Palette smoky', 'Rouge à lèvres intense', 'Mascara volume'] },
  'Nude & minimaliste':  { name: 'Routine Nude',       products: ['BB Cream', 'Mascara naturel', 'Gloss beige', 'Blush pêche'] },
}

export default function BeautyQuiz() {
  const [step, setStep]       = useState(0)
  const [answers, setAnswers] = useState({})
  const [done, setDone]       = useState(false)

  const answer = (key, val) => {
    const next = { ...answers, [key]: val }
    setAnswers(next)
    if (step < STEPS.length - 1) setStep(s => s + 1)
    else setDone(true)
  }

  const result = RESULTS[answers.finish] || RESULTS['Naturel & no-makeup']

  return (
    <div className="makeup-site" style={{ minHeight: '100vh', background: 'var(--beauty-cream)' }}>
      <div style={{ maxWidth: 680, margin: '0 auto', padding: '80px 24px' }}>
        {!done ? (
          <AnimatePresence mode="wait">
            <motion.div key={step} initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }} transition={{ duration: 0.4 }}>
              <div style={{ fontSize: 11, letterSpacing: '0.2em', color: 'var(--beauty-gold)', marginBottom: 16, textTransform: 'uppercase' }}>SIÈCLE BEAUTY — QUIZ {step + 1}/{STEPS.length}</div>
              <h2 style={{ fontSize: 'clamp(22px,4vw,36px)', fontWeight: 700, color: 'var(--beauty-brown)', marginBottom: 40, lineHeight: 1.3, fontFamily: 'var(--beauty-serif)' }}>{STEPS[step].q}</h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                {STEPS[step].opts.map(opt => (
                  <motion.button key={opt} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                    onClick={() => answer(STEPS[step].key, opt)}
                    style={{ padding: '20px 18px', background: '#fff', border: '1px solid var(--beauty-border)', borderRadius: 14, cursor: 'pointer', fontSize: 14, color: 'var(--beauty-brown)', fontWeight: 600, textAlign: 'left', transition: 'all 0.2s' }}>
                    {opt}
                  </motion.button>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 40, justifyContent: 'center' }}>
                {STEPS.map((_, i) => (
                  <div key={i} style={{ width: i === step ? 24 : 8, height: 4, borderRadius: 999, background: i <= step ? 'var(--beauty-gold)' : 'var(--beauty-beige)', transition: 'all 0.3s' }} />
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        ) : (
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <div style={{ fontSize: 11, letterSpacing: '0.2em', color: 'var(--beauty-gold)', marginBottom: 16 }}>VOTRE PROFIL BEAUTÉ</div>
            <h2 style={{ fontSize: 36, fontWeight: 700, color: 'var(--beauty-brown)', marginBottom: 8, fontFamily: 'var(--beauty-serif)' }}>{result.name}</h2>
            <p style={{ color: 'var(--beauty-muted)', marginBottom: 40 }}>Notre sélection personnalisée pour votre routine SIÈCLE BEAUTY.</p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 40 }}>
              {result.products.map(p => (
                <div key={p} style={{ background: '#fff', border: '1px solid var(--beauty-border)', borderRadius: 12, padding: '18px 20px' }}>
                  <div style={{ fontSize: 18, marginBottom: 8 }}>✨</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--beauty-brown)' }}>{p}</div>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 14 }}>
              <a href="/shop/maquillage/?filter=recommended" style={{ padding: '14px 28px', background: 'var(--beauty-brown)', color: '#fff', borderRadius: 8, fontSize: 12, fontWeight: 700, letterSpacing: '0.12em', textDecoration: 'none' }}>VOIR MES PRODUITS</a>
              <button onClick={() => { setStep(0); setAnswers({}); setDone(false) }} style={{ padding: '14px 28px', border: '1px solid var(--beauty-border)', background: 'transparent', color: 'var(--beauty-brown)', borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>RECOMMENCER</button>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}
