import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

export default function LuneaResetPassword() {
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
    if (password.length < 8) { setError('Le mot de passe doit contenir au moins 8 caractères.'); return }
    if (password !== confirm) { setError('Les mots de passe ne correspondent pas.'); return }
    setLoading(true)
    try {
      const res = await fetch('/api/v1/auth/customer/password-reset/confirm/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password, brand_key: 'lunea' }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.error || 'Lien expiré ou invalide.'); return }
      setDone(true)
      setTimeout(() => navigate('/lunea/login/'), 2500)
    } catch {
      setError('Erreur réseau. Veuillez réessayer.')
    } finally {
      setLoading(false)
    }
  }

  const inp = { width: '100%', boxSizing: 'border-box', background: '#fff', border: '1px solid rgba(201,164,92,0.32)', borderRadius: 8, padding: '14px 16px', color: '#3a2a1f', fontSize: 15, outline: 'none' }

  return (
    <main style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fffaf3', padding: '80px 24px' }}>
      <div style={{ width: '100%', maxWidth: 420 }}>
        <p style={{ fontSize: 11, letterSpacing: '0.22em', color: '#c9a45c', textTransform: 'uppercase', marginBottom: 8 }}>LUNEA</p>
        <h1 style={{ fontSize: 'clamp(26px, 4vw, 38px)', fontWeight: 900, color: '#3a2a1f', margin: '0 0 8px', letterSpacing: '-0.04em' }}>Nouveau mot de passe</h1>
        <p style={{ color: '#8a7878', fontSize: 14, lineHeight: 1.7, margin: '0 0 28px' }}>Choisissez votre nouveau mot de passe (8 caractères minimum).</p>

        {error && <p style={{ color: '#C0392B', fontSize: 13, marginBottom: 16 }}>{error}</p>}

        {done ? (
          <div style={{ borderRadius: 12, padding: 20, background: 'rgba(76,175,80,0.1)', border: '1px solid rgba(76,175,80,0.25)', color: '#27AE60', fontSize: 14, lineHeight: 1.7 }}>
            Mot de passe réinitialisé. Redirection vers la connexion...
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {[{ label: 'Nouveau mot de passe', v: password, s: setPassword }, { label: 'Confirmer', v: confirm, s: setConfirm }].map(({ label, v, s }, i) => (
              <div key={i} style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', color: '#8a7878', marginBottom: 8, textTransform: 'uppercase' }}>{label}</label>
                <input type="password" value={v} onChange={e => s(e.target.value)} required minLength={8} style={inp} />
              </div>
            ))}
            <button type="submit" disabled={loading} style={{ width: '100%', padding: 15, marginTop: 8, background: '#c9a45c', color: '#fffaf3', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 800, cursor: 'pointer' }}>
              {loading ? 'Enregistrement...' : 'Enregistrer le mot de passe'}
            </button>
          </form>
        )}
      </div>
    </main>
  )
}
