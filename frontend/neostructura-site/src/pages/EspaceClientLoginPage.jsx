import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import Reveal from '../components/Reveal'
import { useClientAuth } from '../hooks/useClientAuth'

const labelStyle = { display: 'block', fontSize: 12.5, fontWeight: 600, marginBottom: 8, color: 'var(--text-muted)' }
const inputStyle = {
  width: '100%', padding: '12px 14px', borderRadius: 8, border: '1px solid var(--border)',
  background: 'var(--bg)', color: 'var(--text)', fontFamily: 'inherit', fontSize: 14,
}

export default function EspaceClientLoginPage() {
  const { login } = useClientAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await login(email, password)
      navigate('/espace-client')
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Helmet><title>Espace client — NÉOSTRUCTURA</title></Helmet>
      <section style={{
        paddingTop: 'var(--header-h)', minHeight: '92vh',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Reveal className="neo-card" style={{ padding: 44, width: '100%', maxWidth: 420 }}>
          <div className="neo-eyebrow">Espace client</div>
          <h1 style={{ fontSize: 24, marginBottom: 28 }}>Connexion</h1>

          <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div>
              <label style={labelStyle}>Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} style={inputStyle} required />
            </div>
            <div>
              <label style={labelStyle}>Mot de passe</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={inputStyle} required />
            </div>

            {error && <div style={{ color: '#C0392B', fontSize: 13.5 }}>{error}</div>}

            <button type="submit" className="neo-btn neo-btn-primary neo-btn-lg" disabled={submitting} style={{ marginTop: 8 }}>
              {submitting ? 'Connexion…' : 'Se connecter'}
            </button>
          </form>

          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 24, textAlign: 'center' }}>
            Vos accès vous sont communiqués par NÉOSTRUCTURA après acceptation de votre devis.
          </p>
        </Reveal>
      </section>
    </>
  )
}
