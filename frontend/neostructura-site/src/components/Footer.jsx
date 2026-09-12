import { Link } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'
import { METIERS } from '../data/metiers'

export default function Footer() {
  const { dict } = useLanguage()

  return (
    <footer style={{ background: 'var(--surface-brand)', color: 'var(--surface-brand-fg)', paddingTop: 72 }}>
      <div className="neo-container" style={{
        display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1.2fr', gap: 48, paddingBottom: 56,
      }} id="neo-footer-grid">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <span style={{
              width: 28, height: 28, borderRadius: 7, background: '#F7F7F4',
              display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 3, flexShrink: 0,
            }}>
              <img src="/logo-icon.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
            </span>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 20 }}>
              NÉOSTRUCTURA
            </div>
          </div>
          <div className="neo-tag-technical" style={{ borderColor: 'rgba(247,247,244,0.22)', color: 'rgba(247,247,244,0.7)', marginBottom: 16 }}>
            {dict.footer.tagline}
          </div>
          <p style={{ opacity: 0.75, fontSize: 14, lineHeight: 1.7, maxWidth: 320 }}>
            {dict.footer.description}
          </p>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.6, marginBottom: 18 }}>
            {dict.footer.metiersTitle}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {METIERS.map(m => (
              <Link key={m.slug} to="/nos-metiers" style={{ fontSize: 14, opacity: 0.85 }}>
                {dict.metiersContent[m.slug]?.name}
              </Link>
            ))}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.6, marginBottom: 18 }}>
            {dict.footer.companyTitle}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <Link to="/" style={{ fontSize: 14, opacity: 0.85 }}>{dict.footer.companyLinks.home}</Link>
            <Link to="/realisations" style={{ fontSize: 14, opacity: 0.85 }}>{dict.footer.companyLinks.realisations}</Link>
            <Link to="/contact" style={{ fontSize: 14, opacity: 0.85 }}>{dict.footer.companyLinks.contact}</Link>
          </div>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.6, marginBottom: 18 }}>
            {dict.footer.contactTitle}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 14, opacity: 0.85 }}>
            <a href="mailto:contact@neostructura.fr">contact@neostructura.fr</a>
            <a href="tel:+33100000000">01 00 00 00 00</a>
            <span style={{ opacity: 0.7 }}>{dict.footer.zone}</span>
          </div>
        </div>
      </div>

      <div style={{ borderTop: '1px solid rgba(247,247,244,0.14)' }}>
        <div className="neo-container" style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '20px 0', fontSize: 12.5, opacity: 0.6, flexWrap: 'wrap', gap: 8,
        }}>
          <span>© {new Date().getFullYear()} NÉOSTRUCTURA — {dict.footer.rights}</span>
          <span>{dict.footer.poweredBy}</span>
        </div>
      </div>

      <style>{`
        @media (max-width: 860px) {
          #neo-footer-grid { grid-template-columns: 1fr 1fr !important; row-gap: 32px !important; }
        }
        @media (max-width: 560px) {
          #neo-footer-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </footer>
  )
}
