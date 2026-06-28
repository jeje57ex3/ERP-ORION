import { useState } from 'react'
import { Link } from 'react-router-dom'
import MotionPage from '../components/MotionPage'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/api/v1/auth/customer/password-reset/request/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, brand_key: 'siecle' }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.error || 'Une erreur est survenue.')
        return
      }
      setSent(true)
    } catch {
      setError('Erreur réseau. Veuillez réessayer.')
    } finally {
      setLoading(false)
    }
  }

  const fieldStyle = {
    width: '100%', boxSizing: 'border-box',
    background: '#111', border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8, padding: '14px 16px',
    color: '#fff', fontSize: 15, outline: 'none',
  }
  const btnStyle = {
    width: '100%', padding: '15px', marginTop: 20,
    background: 'var(--siecle-beige)', color: '#000',
    border: 'none', borderRadius: 8,
    fontSize: 13, fontWeight: 800, letterSpacing: '0.14em',
    cursor: 'pointer', textTransform: 'uppercase',
  }

  return (
    <MotionPage style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#000', padding: '80px 24px',
    }}>
      <div style={{ width: '100%', maxWidth: 440 }}>
        <p style={{ fontSize: 11, letterSpacing: '0.22em', color: 'var(--siecle-beige)', textTransform: 'uppercase', marginBottom: 8 }}>
          SIÈCLE
        </p>
        <h1 style={{ fontSize: 'clamp(28px, 4vw, 40px)', fontWeight: 900, color: '#fff', margin: '0 0 8px', letterSpacing: '-0.04em' }}>
          Mot de passe oublié
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14, lineHeight: 1.7, margin: '0 0 32px' }}>
          Entrez votre adresse e-mail pour recevoir un lien de réinitialisation.
        </p>

        {error && (
          <p style={{ color: '#FF6464', fontSize: 13, marginBottom: 16 }}>{error}</p>
        )}

        {sent ? (
          <div style={{
            border: '1px solid rgba(76,175,80,0.3)', borderRadius: 12, padding: 20,
            background: 'rgba(76,175,80,0.08)', color: '#4caf50', fontSize: 14, lineHeight: 1.7,
          }}>
            Si un compte existe avec cet email, vous recevrez un lien de réinitialisation.
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', color: '#888', marginBottom: 8, textTransform: 'uppercase' }}>
                Adresse e-mail
              </label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="votre@email.fr"
                required
                autoComplete="email"
                style={fieldStyle}
              />
            </div>
            <button type="submit" disabled={loading} style={btnStyle}>
              {loading ? 'Envoi...' : 'Envoyer le lien'}
            </button>
          </form>
        )}

        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <Link to="/compte/connexion" style={{ color: 'rgba(255,255,255,0.4)', fontSize: 13, textDecoration: 'none' }}>
            ← Retour à la connexion
          </Link>
        </div>
      </div>
    </MotionPage>
  )
}
