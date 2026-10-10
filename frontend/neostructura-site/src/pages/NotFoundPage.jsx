import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useLanguage } from '../i18n/LanguageContext'

export default function NotFoundPage() {
  const { dict } = useLanguage()
  const t = dict.notFound
  return (
    <>
      <Helmet><title>Page introuvable — NÉOSTRUCTURA</title></Helmet>
      <section style={{
        paddingTop: 'var(--header-h)', minHeight: '80vh',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        textAlign: 'center', padding: '0 24px',
      }}>
        <div style={{ fontFamily: 'var(--font-display)', fontSize: 88, color: 'var(--accent)', lineHeight: 1 }}>404</div>
        <h1 style={{ fontSize: 24, margin: '16px 0 12px' }}>{t.title}</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 28 }}>{t.text}</p>
        <Link to="/" className="neo-btn neo-btn-primary">{t.cta}</Link>
      </section>
    </>
  )
}
