import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function NewsletterSection() {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle') // idle | loading | success | error
  const [msg, setMsg] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email) return
    setStatus('loading')
    try {
      const res = await fetch('/api/v1/siecle/newsletter/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      if (res.ok) {
        setStatus('success')
        setMsg('Bienvenue ! Vous êtes inscrit(e).')
        setEmail('')
      } else {
        const data = await res.json().catch(() => ({}))
        setStatus('error')
        setMsg(data.detail || data.email?.[0] || 'Une erreur est survenue.')
      }
    } catch {
      setStatus('error')
      setMsg('Connexion impossible. Veuillez réessayer.')
    }
  }

  return (
    <section style={{
      background: '#f7f1e8',
      padding: '96px 24px',
      textAlign: 'center',
    }}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        style={{ maxWidth: 560, margin: '0 auto' }}
      >
        <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.25em', color: '#c9a45c', marginBottom: 20 }}>
          NEWSLETTER
        </p>

        <h2 style={{
          fontFamily: '"Playfair Display", "Cormorant Garamond", Georgia, serif',
          fontSize: 'clamp(32px, 5vw, 52px)',
          fontWeight: 500, lineHeight: 1.08,
          color: '#090807', letterSpacing: '-0.02em',
          margin: '0 0 20px',
        }}>
          Restez dans le secret.
        </h2>

        <p style={{ fontSize: 15, lineHeight: 1.75, color: '#86796e', marginBottom: 40 }}>
          Nouveautés, lancements exclusifs, conseils beauté et offres réservées à nos abonnés — inscrivez-vous pour ne rien manquer.
        </p>

        <AnimatePresence mode="wait">
          {status === 'success' ? (
            <motion.div
              key="success"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              style={{
                padding: '20px 28px',
                background: 'rgba(201,164,92,0.12)',
                border: '1px solid rgba(201,164,92,0.3)',
                borderRadius: 2,
              }}
            >
              <p style={{ fontSize: 15, color: '#4a3426', fontWeight: 600, margin: 0 }}>
                ✓ {msg}
              </p>
              <p style={{ fontSize: 13, color: '#86796e', marginTop: 8, marginBottom: 0 }}>
                Vous recevrez nos prochaines actualités en avant-première.
              </p>
            </motion.div>
          ) : (
            <motion.form
              key="form"
              onSubmit={handleSubmit}
              style={{ display: 'flex', gap: 0, maxWidth: 460, margin: '0 auto' }}
            >
              <input
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); if (status === 'error') setStatus('idle') }}
                placeholder="Votre adresse e-mail"
                required
                style={{
                  flex: 1,
                  padding: '16px 20px',
                  background: '#fff',
                  border: `1px solid ${status === 'error' ? '#c0392b' : '#ddd0be'}`,
                  borderRight: 'none',
                  fontSize: 14, color: '#090807',
                  outline: 'none',
                  fontFamily: 'Inter, sans-serif',
                }}
                onFocus={e => { e.target.style.borderColor = '#c9a45c' }}
                onBlur={e => { e.target.style.borderColor = status === 'error' ? '#c0392b' : '#ddd0be' }}
              />
              <button
                type="submit"
                disabled={status === 'loading'}
                style={{
                  padding: '16px 24px',
                  background: '#090807',
                  color: '#f7f1e8',
                  border: 'none', cursor: 'pointer',
                  fontSize: 12, fontWeight: 700,
                  letterSpacing: '0.1em',
                  whiteSpace: 'nowrap',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = '#c9a45c' }}
                onMouseLeave={e => { e.currentTarget.style.background = '#090807' }}
              >
                {status === 'loading' ? '…' : "S'inscrire"}
              </button>
            </motion.form>
          )}
        </AnimatePresence>

        {status === 'error' && (
          <p style={{ marginTop: 12, fontSize: 13, color: '#c0392b' }}>{msg}</p>
        )}

        <p style={{ marginTop: 16, fontSize: 11, color: '#86796e', lineHeight: 1.6 }}>
          En vous inscrivant, vous acceptez notre politique de confidentialité. Désinscription possible à tout moment.
        </p>
      </motion.div>
    </section>
  )
}
