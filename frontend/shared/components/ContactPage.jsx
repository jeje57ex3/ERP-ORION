import { useState } from 'react'
import './contact-page.css'

const THEMES = {
  siecle: {
    bg: '#0a0a0a',
    card: '#111',
    border: 'rgba(255,255,255,0.07)',
    accent: '#c9a96e',
    text: '#fff',
    muted: 'rgba(255,255,255,0.45)',
    inputBg: '#1a1a1a',
    inputBorder: 'rgba(255,255,255,0.12)',
    label: 'SIÈCLE',
    tagline: 'Une question, une demande ? Nous vous répondons sous 48h.',
  },
  lunea: {
    bg: '#fdf6ef',
    card: '#fff',
    border: 'rgba(201,164,92,0.15)',
    accent: '#c9a45c',
    text: '#3a2a1f',
    muted: '#9a8a7a',
    inputBg: '#fdf6ef',
    inputBorder: 'rgba(201,164,92,0.25)',
    label: 'LUNEA',
    tagline: 'Une question, une demande ? Nous vous répondons sous 48h.',
  },
}

const SUBJECTS = [
  'Commande & livraison',
  'Retour & remboursement',
  'Produit & conseil',
  'Compte client',
  'Presse & partenariat',
  'Autre',
]

export default function ContactPage({ brand = 'siecle' }) {
  const t = THEMES[brand] || THEMES.siecle
  const [form, setForm] = useState({ name: '', email: '', subject: '', message: '', website: '' })
  const [status, setStatus] = useState(null) // null | 'sending' | 'ok' | 'error'

  function set(field) {
    return e => setForm(prev => ({ ...prev, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (status === 'sending' || status === 'ok') return
    setStatus('sending')
    try {
      const res = await fetch('/api/v1/contact/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, brand_key: brand }),
      })
      if (res.ok) {
        setStatus('ok')
        setForm({ name: '', email: '', subject: '', message: '', website: '' })
      } else {
        setStatus('error')
      }
    } catch {
      setStatus('error')
    }
  }

  const inputStyle = {
    width: '100%',
    background: t.inputBg,
    border: `1px solid ${t.inputBorder}`,
    borderRadius: 6,
    padding: '12px 14px',
    color: t.text,
    fontSize: 14,
    outline: 'none',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
  }

  return (
    <div className={`contact-page contact-${brand}`} style={{ background: t.bg, minHeight: '100vh', paddingTop: 'var(--header-h, 80px)' }}>
      {/* Hero */}
      <div style={{ textAlign: 'center', padding: '64px 24px 48px' }}>
        <p style={{ fontSize: 11, fontWeight: 800, letterSpacing: '0.22em', color: t.accent, marginBottom: 16 }}>
          CONTACT
        </p>
        <h1 style={{ fontSize: 'clamp(28px, 5vw, 48px)', fontWeight: 900, color: t.text, letterSpacing: '0.04em', margin: '0 0 16px' }}>
          {t.label}
        </h1>
        <p style={{ color: t.muted, fontSize: 15, maxWidth: 480, margin: '0 auto' }}>
          {t.tagline}
        </p>
      </div>

      {/* Form card */}
      <div style={{ maxWidth: 620, margin: '0 auto', padding: '0 24px 80px' }}>
        <div style={{
          background: t.card,
          border: `1px solid ${t.border}`,
          borderRadius: 12,
          padding: 'clamp(24px, 5vw, 48px)',
        }}>
          {status === 'ok' ? (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <div style={{ fontSize: 40, marginBottom: 16 }}>✓</div>
              <p style={{ fontSize: 18, fontWeight: 700, color: t.accent, marginBottom: 8 }}>Message envoyé</p>
              <p style={{ color: t.muted, fontSize: 14 }}>Nous vous répondrons dans les meilleurs délais.</p>
              <button
                onClick={() => setStatus(null)}
                style={{ marginTop: 24, background: 'none', border: `1px solid ${t.accent}`, color: t.accent, padding: '10px 24px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}
              >
                Nouveau message
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Honeypot — hidden from real users */}
              <input
                type="text"
                name="website"
                value={form.website}
                onChange={set('website')}
                tabIndex={-1}
                aria-hidden="true"
                style={{ display: 'none' }}
              />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: t.muted, marginBottom: 8 }}>
                    NOM *
                  </label>
                  <input
                    required
                    type="text"
                    value={form.name}
                    onChange={set('name')}
                    placeholder="Votre nom"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: t.muted, marginBottom: 8 }}>
                    EMAIL *
                  </label>
                  <input
                    required
                    type="email"
                    value={form.email}
                    onChange={set('email')}
                    placeholder="votre@email.fr"
                    style={inputStyle}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: t.muted, marginBottom: 8 }}>
                  SUJET *
                </label>
                <select
                  required
                  value={form.subject}
                  onChange={set('subject')}
                  style={{ ...inputStyle, cursor: 'pointer' }}
                >
                  <option value="">Sélectionnez un sujet</option>
                  {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', color: t.muted, marginBottom: 8 }}>
                  MESSAGE *
                </label>
                <textarea
                  required
                  value={form.message}
                  onChange={set('message')}
                  placeholder="Décrivez votre demande..."
                  rows={6}
                  style={{ ...inputStyle, resize: 'vertical' }}
                />
              </div>

              {status === 'error' && (
                <p style={{ color: '#e57373', fontSize: 13, margin: 0 }}>
                  Une erreur est survenue. Veuillez réessayer.
                </p>
              )}

              <button
                type="submit"
                disabled={status === 'sending'}
                style={{
                  background: t.accent,
                  color: brand === 'siecle' ? '#0a0a0a' : '#fff',
                  border: 'none',
                  borderRadius: 6,
                  padding: '14px 32px',
                  fontSize: 13,
                  fontWeight: 800,
                  letterSpacing: '0.12em',
                  cursor: status === 'sending' ? 'wait' : 'pointer',
                  opacity: status === 'sending' ? 0.7 : 1,
                  transition: 'opacity 0.2s',
                }}
              >
                {status === 'sending' ? 'ENVOI EN COURS…' : 'ENVOYER'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
