import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import MotionPage from '../components/MotionPage'

export default function ResetPassword() {
  const { token } = useParams()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Le mot de passe doit contenir au moins 8 caractères.')
      return
    }
    if (password !== confirm) {
      setError('Les mots de passe ne correspondent pas.')
      return
    }
    setLoading(true)
    try {
      const res = await fetch('/api/v1/auth/customer/password-reset/confirm/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password, brand_key: 'siecle' }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.error || 'Lien expiré ou invalide.')
        return
      }
      setDone(true)
      setTimeout(() => navigate('/compte/connexion'), 2500)
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
          Nouveau mot de passe
        </h1>
        <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 14, lineHeight: 1.7, margin: '0 0 32px' }}>
          Choisissez votre nouveau mot de passe (8 caractères minimum).
        </p>

        {error && <p style={{ color: '#FF6464', fontSize: 13, marginBottom: 16 }}>{error}</p>}

        {done ? (
          <div style={{
            border: '1px solid rgba(76,175,80,0.3)', borderRadius: 12, padding: 20,
            background: 'rgba(76,175,80,0.08)', color: '#4caf50', fontSize: 14, lineHeight: 1.7,
          }}>
            Mot de passe réinitialisé. Redirection vers la connexion...
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {[
              { label: 'Nouveau mot de passe', value: password, setter: setPassword, id: 'pwd' },
              { label: 'Confirmer le mot de passe', value: confirm, setter: setConfirm, id: 'cpwd' },
            ].map(({ label, value, setter, id }) => (
              <div key={id} style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', color: '#888', marginBottom: 8, textTransform: 'uppercase' }}>
                  {label}
                </label>
                <input
                  type="password"
                  id={id}
                  value={value}
                  onChange={e => setter(e.target.value)}
                  required
                  minLength={8}
                  style={fieldStyle}
                />
              </div>
            ))}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%', padding: '15px', marginTop: 8,
                background: 'var(--siecle-beige)', color: '#000',
                border: 'none', borderRadius: 8,
                fontSize: 13, fontWeight: 800, letterSpacing: '0.14em',
                cursor: 'pointer', textTransform: 'uppercase',
              }}
            >
              {loading ? 'Enregistrement...' : 'Enregistrer le mot de passe'}
            </button>
          </form>
        )}
      </div>
    </MotionPage>
  )
}
