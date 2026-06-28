import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { login, register, setAuthToken } from '../api/customer'

export default function Login({ mode = 'login' }) {
  const [isRegister, setIsRegister] = useState(mode === 'register')
  const [form, setForm] = useState({ email: '', password: '', first_name: '', last_name: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const fn = isRegister ? register : login
      const data = await fn(form)
      if (data.token) {
        setAuthToken(data.token)
        localStorage.setItem('siecle_token', data.token)
      }
      navigate('/compte')
    } catch (err) {
      const d = err?.response?.data
      setError(d?.error || d?.email?.[0] || d?.password?.[0] || 'Une erreur est survenue.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', background: '#000',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '80px 24px',
    }}>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ width: '100%', maxWidth: 420 }}
      >
        <Link to="/" style={{
          display: 'block', textAlign: 'center',
          fontFamily: 'Montserrat, sans-serif',
          fontSize: 22, fontWeight: 900, color: '#fff',
          letterSpacing: '0.08em', marginBottom: 48,
        }}>
          SIÈCLE
        </Link>

        <div style={{
          background: '#111', border: '1px solid rgba(255,255,255,0.06)',
          padding: 40,
        }}>
          <div style={{ display: 'flex', gap: 0, marginBottom: 32 }}>
            {['SE CONNECTER', 'S\'INSCRIRE'].map((label, i) => (
              <button
                key={label}
                onClick={() => setIsRegister(i === 1)}
                style={{
                  flex: 1, padding: '10px 0',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: `2px solid ${(i === 0 && !isRegister) || (i === 1 && isRegister) ? '#C0A882' : 'rgba(255,255,255,0.08)'}`,
                  color: (i === 0 && !isRegister) || (i === 1 && isRegister) ? '#fff' : 'rgba(255,255,255,0.35)',
                  fontSize: 11, fontWeight: 700, letterSpacing: '0.14em',
                  cursor: 'pointer', transition: 'all 0.2s',
                }}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {isRegister && (
              <>
                <input
                  type="text" placeholder="Prénom" value={form.first_name}
                  onChange={set('first_name')}
                  style={inputStyle}
                />
                <input
                  type="text" placeholder="Nom" value={form.last_name}
                  onChange={set('last_name')}
                  style={inputStyle}
                />
              </>
            )}
            <input
              type="email" placeholder="Adresse e-mail" required value={form.email}
              onChange={set('email')}
              style={inputStyle}
            />
            <input
              type="password" placeholder="Mot de passe" required value={form.password}
              onChange={set('password')} minLength={isRegister ? 8 : undefined}
              style={inputStyle}
            />

            {error && (
              <p style={{ fontSize: 13, color: '#E07070' }}>{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '14px', marginTop: 8,
                background: '#fff', color: '#000',
                border: 'none', cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: 11, fontWeight: 800, letterSpacing: '0.16em',
                opacity: loading ? 0.6 : 1, transition: 'opacity 0.2s',
              }}
            >
              {loading ? '...' : isRegister ? 'CRÉER MON COMPTE' : 'SE CONNECTER'}
            </button>
          </form>
        </div>
      </motion.div>
    </div>
  )
}

const inputStyle = {
  padding: '12px 14px',
  background: '#000',
  border: '1px solid rgba(255,255,255,0.1)',
  color: '#fff', fontSize: 14,
  outline: 'none', width: '100%',
  boxSizing: 'border-box',
}
