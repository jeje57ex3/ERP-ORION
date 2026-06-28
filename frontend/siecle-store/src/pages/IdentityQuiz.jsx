import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import PageTransition from '../components/PageTransition'
import { fadeUp, staggerContainer } from '../utils/animations'

const STEPS = [
  {
    q: 'Quel style vous représente le mieux ?',
    key: 'style',
    options: ['Minimaliste et épuré', 'Sombre et affirmé', 'Élégant et classique', 'Urbain et moderne', 'Audacieux et fort'],
  },
  {
    q: 'Quelle couleur portez-vous le plus souvent ?',
    key: 'color',
    options: ['Noir', 'Blanc / Crème', 'Tons neutres', 'Couleurs vives', 'Camaïeu sombre'],
  },
  {
    q: 'Quelle silhouette préférez-vous ?',
    key: 'silhouette',
    options: ['Discrète et sobre', 'Imposante et visible', 'Équilibrée et fluide', 'Structure et ajustée'],
  },
  {
    q: 'Quel univers vous attire le plus ?',
    key: 'universe',
    options: ['Vêtements', 'Montres', 'Maquillage', 'Les trois à égalité'],
  },
  {
    q: 'Votre occasion principale ?',
    key: 'occasion',
    options: ['Quotidien', 'Soirée', 'Professionnel', 'Événements exclusifs'],
  },
]

const IDENTITY_MAP = {
  'Minimaliste et épuré': 'minimal',
  'Sombre et affirmé':    'nuit',
  'Élégant et classique': 'elegance',
  'Urbain et moderne':    'urbain',
  'Audacieux et fort':    'audace',
}

const IDENTITY_DATA = {
  minimal:   { label: 'MINIMAL',   color: '#C8B89A', desc: 'L\'essentiel, rien de plus. Vous choisissez chaque pièce avec précision.', icon: '—' },
  nuit:      { label: 'NUIT',      color: '#9090B0', desc: 'Sombre, affirmé, singulier. Vous portez la nuit comme une seconde peau.', icon: '◆' },
  elegance:  { label: 'ÉLÉGANCE',  color: '#D4B896', desc: 'Raffinement classique. Chaque détail parle de savoir-faire.', icon: '◇' },
  urbain:    { label: 'URBAIN',    color: '#A0A0A0', desc: 'Moderne, mobile, ancré dans le présent. La rue comme terrain de jeu.', icon: '⬡' },
  audace:    { label: 'AUDACE',    color: '#C05070', desc: 'Vous êtes le regard. Chaque tenue est une déclaration.', icon: '✦' },
  signature: { label: 'SIGNATURE', color: '#C9A45C', desc: 'Vous avez votre propre code. SIÈCLE amplifie ce qui vous définit.', icon: '✦' },
}

export default function IdentityQuiz() {
  const [step,    setStep]    = useState(0)
  const [answers, setAnswers] = useState({})
  const [result,  setResult]  = useState(null)
  const navigate = useNavigate()

  const choose = (opt) => {
    const next = { ...answers, [STEPS[step].key]: opt }
    setAnswers(next)
    if (step + 1 < STEPS.length) {
      setStep(s => s + 1)
    } else {
      const identity = IDENTITY_MAP[next.style] || 'signature'
      setResult(identity)
      fetch('/api/v1/siecle/identity-quiz/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers: next }),
      }).catch(() => {})
    }
  }

  const reset = () => { setStep(0); setAnswers({}); setResult(null) }

  const progress = ((step) / STEPS.length) * 100

  return (
    <PageTransition>
      <div style={{ minHeight: '100vh', background: '#000', color: '#fff', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 24px' }}>

        {!result ? (
          <>
            {/* Progress bar */}
            <div style={{ width: '100%', maxWidth: 600, height: 1, background: 'rgba(255,255,255,0.1)', marginBottom: 60 }}>
              <motion.div
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.4 }}
                style={{ height: '100%', background: 'var(--siecle-beige)' }}
              />
            </div>

            <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.24em', color: 'var(--siecle-beige)', marginBottom: 16 }}>
              {step + 1} / {STEPS.length}
            </p>

            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.3 }}
                style={{ width: '100%', maxWidth: 600, textAlign: 'center' }}
              >
                <h2 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: 'clamp(20px, 3vw, 28px)', fontWeight: 900, marginBottom: 48, lineHeight: 1.3 }}>
                  {STEPS[step].q}
                </h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {STEPS[step].options.map(opt => (
                    <motion.button
                      key={opt}
                      whileHover={{ background: 'rgba(192,168,130,0.08)', borderColor: 'rgba(192,168,130,0.4)' }}
                      onClick={() => choose(opt)}
                      style={{
                        padding: '16px 24px',
                        background: 'rgba(255,255,255,0.03)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        color: '#fff',
                        fontSize: 14,
                        cursor: 'pointer',
                        letterSpacing: '0.04em',
                        textAlign: 'left',
                        transition: 'all 0.2s',
                      }}
                    >
                      {opt}
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            </AnimatePresence>
          </>
        ) : (
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6 }}
            style={{ textAlign: 'center', maxWidth: 540 }}
          >
            <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', color: 'var(--siecle-beige)', marginBottom: 24 }}>
              VOTRE IDENTITÉ SIÈCLE
            </p>
            <p style={{ fontSize: 80, marginBottom: 16 }}>{IDENTITY_DATA[result]?.icon}</p>
            <h2 style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 'clamp(40px, 8vw, 72px)',
              fontWeight: 900,
              color: IDENTITY_DATA[result]?.color,
              letterSpacing: '0.08em',
              marginBottom: 24,
            }}>
              {IDENTITY_DATA[result]?.label}
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.55)', fontSize: 15, lineHeight: 1.8, marginBottom: 48 }}>
              {IDENTITY_DATA[result]?.desc}
            </p>
            <div style={{ display: 'flex', gap: 16, justifyContent: 'center', flexWrap: 'wrap' }}>
              <button
                onClick={() => navigate('/boutique')}
                style={{ padding: '14px 32px', background: 'var(--siecle-beige)', color: '#000', border: 'none', fontSize: 11, fontWeight: 800, letterSpacing: '0.14em', cursor: 'pointer' }}
              >
                EXPLORER MA SÉLECTION
              </button>
              <button
                onClick={reset}
                style={{ padding: '14px 32px', background: 'transparent', color: 'rgba(255,255,255,0.4)', border: '1px solid rgba(255,255,255,0.15)', fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', cursor: 'pointer' }}
              >
                RECOMMENCER
              </button>
            </div>
          </motion.div>
        )}
      </div>
    </PageTransition>
  )
}
