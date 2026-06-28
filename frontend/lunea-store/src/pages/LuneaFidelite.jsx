import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'

const TIERS = [
  { key: 'jade', label: 'Jade', min: 0, max: 499, color: '#6B7280', icon: '💚' },
  { key: 'ambre', label: 'Ambre', min: 500, max: 1499, color: '#C6A15B', icon: '🟡' },
  { key: 'nacre', label: 'Nacre', min: 1500, max: 2999, color: '#c8956b', icon: '🌸' },
  { key: 'lune', label: 'Lune', min: 3000, max: Infinity, color: '#8B5CF6', icon: '🌙' },
]

function getTier(points) {
  return TIERS.find(t => points >= t.min && points <= t.max) || TIERS[0]
}

export default function LuneaFidelite() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    document.title = 'Fidélité LUNEA — Mon programme'
    fetch('/api/v1/lunea/customer/rewards/', { credentials: 'include' })
      .then(r => {
        if (r.status === 401) { navigate('/lunea/login/'); return null }
        return r.ok ? r.json() : null
      })
      .then(d => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [navigate])

  if (loading) {
    return (
      <div style={{ paddingTop: 'var(--header-h)', minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--color-text-muted)' }}>Chargement...</p>
      </div>
    )
  }

  const points = data?.points ?? 0
  const tier = getTier(points)
  const nextTier = TIERS[TIERS.indexOf(tier) + 1]
  const progress = nextTier ? Math.min(100, ((points - tier.min) / (nextTier.min - tier.min)) * 100) : 100

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      <section className="lunea-section">
        <div className="lunea-container" style={{ maxWidth: 760 }}>
          <Link to="/lunea/compte/" style={{ fontSize: 12, color: 'var(--color-text-muted)', textDecoration: 'none', marginBottom: '1.5rem', display: 'inline-block' }}>
            ← Mon compte
          </Link>
          <p className="lunea-eyebrow">Fidélité</p>
          <h1 className="lunea-heading" style={{ marginBottom: '2rem' }}>Programme LUNEA</h1>

          {/* Current status */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            style={{
              background: `linear-gradient(135deg, ${tier.color}15, var(--color-surface))`,
              border: `1px solid ${tier.color}40`,
              borderRadius: 'var(--radius)', padding: '2rem',
              marginBottom: '2rem', textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 48, marginBottom: 12 }}>{tier.icon}</div>
            <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.4rem', color: tier.color, marginBottom: 8 }}>
              Statut {tier.label}
            </p>
            <p style={{ fontSize: '2.5rem', fontFamily: 'var(--font-heading)', fontWeight: 300, marginBottom: 4 }}>
              {points.toLocaleString('fr-FR')}
            </p>
            <p style={{ fontSize: 13, color: 'var(--color-text-muted)' }}>points LUNEA</p>

            {nextTier && (
              <div style={{ marginTop: '1.5rem', maxWidth: 400, margin: '1.5rem auto 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                  <span>{tier.label}</span>
                  <span>{nextTier.label} ({(nextTier.min - points).toLocaleString('fr-FR')} pts)</span>
                </div>
                <div style={{ height: 6, borderRadius: 3, background: 'var(--color-border)', overflow: 'hidden' }}>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 1.2, delay: 0.3 }}
                    style={{ height: '100%', background: tier.color, borderRadius: 3 }}
                  />
                </div>
              </div>
            )}
          </motion.div>

          {/* Tiers overview */}
          <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', fontWeight: 400, marginBottom: '1rem' }}>
            Les niveaux du programme
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: '2rem' }}>
            {TIERS.map(t => (
              <div key={t.key} style={{
                background: 'var(--color-surface)', border: `1px solid ${t.key === tier.key ? t.color : 'var(--color-border)'}`,
                borderRadius: 'var(--radius)', padding: '1rem', textAlign: 'center',
                opacity: t.min > points ? 0.55 : 1,
              }}>
                <div style={{ fontSize: 24, marginBottom: 6 }}>{t.icon}</div>
                <p style={{ fontFamily: 'var(--font-heading)', fontSize: '0.9rem', color: t.color }}>{t.label}</p>
                <p style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                  {t.max === Infinity ? `${t.min.toLocaleString('fr-FR')}+ pts` : `${t.min.toLocaleString('fr-FR')} – ${t.max.toLocaleString('fr-FR')} pts`}
                </p>
              </div>
            ))}
          </div>

          {/* Rewards history */}
          {data?.history && data.history.length > 0 && (
            <>
              <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', fontWeight: 400, marginBottom: '1rem' }}>
                Historique des points
              </h2>
              {data.history.map((h, i) => (
                <div key={i} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '10px 0', borderBottom: '1px solid var(--color-border)',
                  fontSize: 14,
                }}>
                  <div>
                    <p>{h.label}</p>
                    <p style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                      {h.date ? new Date(h.date).toLocaleDateString('fr-FR') : ''}
                    </p>
                  </div>
                  <span style={{ fontFamily: 'var(--font-heading)', color: h.points > 0 ? '#16A34A' : '#DC2626' }}>
                    {h.points > 0 ? '+' : ''}{h.points} pts
                  </span>
                </div>
              ))}
            </>
          )}
        </div>
      </section>
    </div>
  )
}
