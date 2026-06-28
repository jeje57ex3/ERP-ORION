import { Link } from 'react-router-dom'

export default function LuneaCheckoutCancel() {
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
          background: 'rgba(255,100,100,0.1)',
          border: '2px solid rgba(255,100,100,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 28px', fontSize: 28, color: '#e57373',
        }}>
          ×
        </div>

        <p style={{ margin: '0 0 10px', fontSize: 11, letterSpacing: '0.22em', textTransform: 'uppercase', color: '#c9a45c' }}>
          LUNEA
        </p>
        <h1 style={{ margin: '0 0 16px', fontSize: 'clamp(28px, 5vw, 48px)', fontWeight: 900, letterSpacing: '-0.05em', color: '#3a2a1f' }}>
          Paiement non finalisé
        </h1>
        <p style={{ margin: '0 0 32px', color: '#6d5a50', fontSize: 15, lineHeight: 1.7 }}>
          Votre paiement n'a pas été confirmé. Votre panier a été conservé.
        </p>

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link to="/lunea/panier/" style={{
            padding: '14px 24px', background: '#c9a45c', color: '#fffaf3',
            textDecoration: 'none', borderRadius: 999, fontSize: 13, fontWeight: 800,
          }}>
            Retour au panier
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
