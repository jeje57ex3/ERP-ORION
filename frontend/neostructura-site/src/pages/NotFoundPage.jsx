import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'

export default function NotFoundPage() {
  return (
    <>
      <Helmet><title>Page introuvable — NÉOSTRUCTURA</title></Helmet>
      <section style={{
        paddingTop: 'var(--header-h)', minHeight: '80vh',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        textAlign: 'center', padding: '0 24px',
      }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 88, color: 'var(--accent)', lineHeight: 1 }}>404</div>
        <h1 style={{ fontSize: 24, margin: '16px 0 12px' }}>Page introuvable</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 28 }}>Cette page n'existe pas ou plus.</p>
        <Link to="/" className="neo-btn neo-btn-primary">Retour à l'accueil</Link>
      </section>
    </>
  )
}
