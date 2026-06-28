import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

export default function LuneaCompte() {
  const [account, setAccount] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    document.title = 'Mon compte — LUNEA'
    fetch('/api/v1/lunea/customer/account/', { credentials: 'include' })
      .then(r => {
        if (r.status === 401) { navigate('/lunea/login/'); return null }
        return r.ok ? r.json() : null
      })
      .then(d => setAccount(d))
      .catch(() => setAccount(null))
      .finally(() => setLoading(false))
  }, [navigate])

  async function handleLogout() {
    await fetch('/api/v1/auth/customer/logout/', { method: 'POST', credentials: 'include' })
    window.location.href = '/lunea/'
  }

  if (loading) {
    return (
      <div style={{ paddingTop: 'var(--header-h)', minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--color-text-muted)' }}>Chargement...</p>
      </div>
    )
  }

  if (!account) {
    return (
      <div style={{ paddingTop: 'var(--header-h)', minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <p className="lunea-eyebrow">Compte</p>
          <p style={{ fontSize: 14, color: 'var(--color-text-muted)', marginBottom: '2rem' }}>Connectez-vous pour accéder à votre espace personnel.</p>
          <Link to="/lunea/login/" className="btn-primary">Se connecter</Link>
        </div>
      </div>
    )
  }

  const sections = [
    { label: 'Mes commandes', icon: '📦', desc: 'Suivre et gérer vos commandes', to: '/lunea/compte/commandes/' },
    { label: 'Mon programme fidélité', icon: '✨', desc: `${account.reward_points ?? 0} points LUNEA`, to: '/lunea/compte/fidelite/' },
    { label: 'Ma liste de souhaits', icon: '🤍', desc: 'Produits sauvegardés', to: '/lunea/boutique/?wishlist=true' },
  ]

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      <section className="lunea-section">
        <div className="lunea-container" style={{ maxWidth: 800 }}>
          <p className="lunea-eyebrow">Espace personnel</p>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16, marginBottom: '2.5rem' }}>
            <h1 className="lunea-heading">Bonjour, {account.first_name || account.email}</h1>
            <button onClick={handleLogout}
              style={{ fontSize: 13, color: 'var(--color-text-muted)', background: 'none', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: '6px 16px', cursor: 'pointer' }}>
              Déconnexion
            </button>
          </div>

          {/* Account info */}
          <div style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius)', padding: '1.25rem 1.5rem', marginBottom: '2rem' }}>
            <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 4 }}>Email</p>
            <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>{account.email}</p>
            {account.phone && (
              <>
                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 4, marginTop: 12 }}>Téléphone</p>
                <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>{account.phone}</p>
              </>
            )}
          </div>

          {/* Navigation sections */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16 }}>
            {sections.map(s => (
              <Link key={s.label} to={s.to} style={{ textDecoration: 'none' }}>
                <div style={{
                  background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius)', padding: '1.5rem',
                  transition: 'border-color 0.2s',
                }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                  onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--color-border)'}
                >
                  <div style={{ fontSize: 28, marginBottom: 10 }}>{s.icon}</div>
                  <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem', fontWeight: 400, marginBottom: 4 }}>{s.label}</p>
                  <p style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{s.desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
