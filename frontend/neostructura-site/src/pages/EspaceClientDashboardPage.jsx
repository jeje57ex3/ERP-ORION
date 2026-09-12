import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import Reveal from '../components/Reveal'
import { useClientAuth } from '../hooks/useClientAuth'
import { portalFetchDashboard } from '../api/portal'
import { useLanguage } from '../i18n/LanguageContext'

const STATUS_COLORS = {
  study: 'var(--text-muted)', quoted: '#B8860B', won: 'var(--accent)',
  in_progress: 'var(--accent)', completed: '#2E7D32', invoiced: '#2E7D32', guaranteed: '#2E7D32',
}

export default function EspaceClientDashboardPage() {
  const { dict } = useLanguage()
  const t = dict.portal
  const { account, loading, isAuthenticated, logout } = useClientAuth()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (loading) return
    if (!isAuthenticated) { navigate('/espace-client/connexion'); return }
    portalFetchDashboard().then(setData).catch(err => setError(err.message))
  }, [loading, isAuthenticated])

  const onLogout = async () => {
    await logout()
    navigate('/espace-client/connexion')
  }

  if (loading || (!data && !error)) {
    return (
      <section style={{ paddingTop: 'var(--header-h)', minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>{t.loading}</p>
      </section>
    )
  }

  return (
    <>
      <Helmet><title>Mon espace — NÉOSTRUCTURA</title></Helmet>

      <section style={{ paddingTop: 'calc(var(--header-h) + 48px)', paddingBottom: 96 }}>
        <div className="neo-container">
          <Reveal style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 40, flexWrap: 'wrap', gap: 16 }}>
            <div>
              <div className="neo-eyebrow">{t.eyebrow}</div>
              <h1 style={{ fontSize: 'clamp(24px, 3.2vw, 34px)' }}>
                {t.greeting(data?.account?.first_name || account?.first_name)}
              </h1>
            </div>
            <button className="neo-btn neo-btn-outline" onClick={onLogout}>{t.logout}</button>
          </Reveal>

          {error && <p style={{ color: '#C0392B' }}>{error}</p>}

          {data && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20, marginBottom: 48 }} id="neo-dash-kpis">
                {[
                  { label: t.kpiProjects, value: data.projects.length },
                  { label: t.kpiRequests, value: data.requests.length },
                  { label: t.kpiNotifications, value: data.notifications.length },
                ].map(kpi => (
                  <div key={kpi.label} className="neo-card" style={{ padding: 24, textAlign: 'center' }}>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: 32, color: 'var(--accent)', fontWeight: 600 }}>{kpi.value}</div>
                    <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6 }}>{kpi.label}</div>
                  </div>
                ))}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 32 }} id="neo-dash-layout">
                <div>
                  <h2 style={{ fontSize: 18, marginBottom: 18 }}>{t.myProjects}</h2>
                  {data.projects.length === 0 ? (
                    <div className="neo-card" style={{ padding: 28, color: 'var(--text-muted)', fontSize: 14 }}>
                      {t.noProjects}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {data.projects.map(p => (
                        <div key={p.id} className="neo-card" style={{ padding: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 14.5 }}>{p.name}</div>
                            <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{p.city}</div>
                          </div>
                          <span className="neo-badge" style={{ color: STATUS_COLORS[p.status] || 'var(--text-muted)' }}>
                            {p.status_label}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  <h2 style={{ fontSize: 18, margin: '36px 0 18px' }}>{t.myRequests}</h2>
                  {data.requests.length === 0 ? (
                    <div className="neo-card" style={{ padding: 28, color: 'var(--text-muted)', fontSize: 14 }}>
                      {t.noRequests}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {data.requests.map(r => (
                        <div key={r.reference} className="neo-card" style={{ padding: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 14.5 }}>{r.request_type_label}</div>
                            <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{t.reference} {r.reference}</div>
                          </div>
                          <span className="neo-badge">{r.status_label}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <h2 style={{ fontSize: 18, marginBottom: 18 }}>{t.notifications}</h2>
                  {data.notifications.length === 0 ? (
                    <div className="neo-card" style={{ padding: 28, color: 'var(--text-muted)', fontSize: 14 }}>
                      {t.noNotifications}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {data.notifications.map(n => (
                        <div key={n.id} className="neo-card" style={{ padding: 16 }}>
                          <div style={{ fontWeight: 600, fontSize: 13.5, marginBottom: 4 }}>{n.title}</div>
                          <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{n.message}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </section>

      <style>{`
        @media (max-width: 900px) {
          #neo-dash-kpis { grid-template-columns: 1fr !important; }
          #neo-dash-layout { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  )
}
