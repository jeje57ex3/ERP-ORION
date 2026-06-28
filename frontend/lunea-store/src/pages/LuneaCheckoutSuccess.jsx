import { useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

export default function LuneaCheckoutSuccess() {
  const [searchParams] = useSearchParams()
  const sessionId = searchParams.get('session_id')

  useEffect(() => {
    try {
      localStorage.removeItem('lunea_cart')
    } catch {}
  }, [])

  return (
    <main style={{
      minHeight: '100vh',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#fffaf3', padding: '60px 24px',
    }}>
      <div style={{
        width: '100%', maxWidth: 560,
        border: '1px solid rgba(201,164,92,0.24)', borderRadius: 30,
        padding: 'clamp(32px, 6vw, 64px)',
        background: 'rgba(232,200,191,0.14)', textAlign: 'center',
      }}>
        <div style={{
          width: 72, height: 72, borderRadius: '50%',
          background: 'rgba(76,175,80,0.14)',
          border: '2px solid rgba(76,175,80,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 28px', fontSize: 28, color: '#4caf50',
        }}>
          ✓
        </div>

        <p style={{ margin: '0 0 10px', fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', color: '#c9a45c' }}>
          LUNEA
        </p>
        <h1 style={{ margin: '0 0 16px', fontSize: 'clamp(28px, 5vw, 48px)', fontWeight: 900, letterSpacing: '-0.05em', color: '#3a2a1f' }}>
          Commande confirmée
        </h1>
        <p style={{ margin: '0 0 8px', color: '#6d5a50', fontSize: 15, lineHeight: 1.7 }}>
          Merci pour votre commande. Un email de confirmation vient de vous être envoyé.
        </p>
        {sessionId && (
          <p style={{ margin: '0 0 32px', color: '#b8a89a', fontSize: 11, letterSpacing: '0.06em' }}>
            Référence : {sessionId.slice(-10).toUpperCase()}
          </p>
        )}

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link to="/lunea/compte/commandes/" style={{
            padding: '14px 24px', background: '#c9a45c', color: '#fffaf3',
            textDecoration: 'none', borderRadius: 999, fontSize: 13, fontWeight: 800,
          }}>
            Mes commandes
          </Link>
          <Link to="/lunea/" style={{
            padding: '14px 24px',
            border: '1px solid rgba(201,164,92,0.32)',
            color: '#3a2a1f', textDecoration: 'none', borderRadius: 999, fontSize: 13, fontWeight: 700,
          }}>
            Retour à l'accueil
          </Link>
        </div>
      </div>
    </main>
  )
}
