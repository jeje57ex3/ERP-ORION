import { Link } from 'react-router-dom'

const METIERS = [
  'Électricité générale', 'Domotique', 'Étanchéité',
  'Informatique & Réseaux', 'Rénovation', 'Maintenance',
]

export default function Footer() {
  return (
    <footer style={{ background: 'var(--surface-brand)', color: 'var(--surface-brand-fg)', paddingTop: 72 }}>
      <div className="neo-container" style={{
        display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr 1.2fr', gap: 48, paddingBottom: 56,
      }} id="neo-footer-grid">
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 22, marginBottom: 16 }}>
            NÉOSTRUCTURA
          </div>
          <p style={{ opacity: 0.75, fontSize: 14, lineHeight: 1.7, maxWidth: 320 }}>
            Électricité générale, domotique, informatique &amp; réseaux, étanchéité, rénovation et
            maintenance. Un interlocuteur unique pour tous vos projets techniques.
          </p>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.6, marginBottom: 18 }}>
            Nos métiers
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {METIERS.map(m => (
              <Link key={m} to="/nos-metiers" style={{ fontSize: 14, opacity: 0.85 }}>{m}</Link>
            ))}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.6, marginBottom: 18 }}>
            Entreprise
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <Link to="/" style={{ fontSize: 14, opacity: 0.85 }}>Accueil</Link>
            <Link to="/realisations" style={{ fontSize: 14, opacity: 0.85 }}>Réalisations</Link>
            <Link to="/contact" style={{ fontSize: 14, opacity: 0.85 }}>Contact</Link>
          </div>
        </div>

        <div>
          <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.6, marginBottom: 18 }}>
            Contact
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 14, opacity: 0.85 }}>
            <a href="mailto:contact@neostructura.fr">contact@neostructura.fr</a>
            <a href="tel:+33100000000">01 00 00 00 00</a>
            <span style={{ opacity: 0.7 }}>Intervention dans toute la région</span>
          </div>
        </div>
      </div>

      <div style={{ borderTop: '1px solid rgba(247,247,244,0.14)' }}>
        <div className="neo-container" style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '20px 0', fontSize: 12.5, opacity: 0.6, flexWrap: 'wrap', gap: 8,
        }}>
          <span>© {new Date().getFullYear()} NÉOSTRUCTURA — Tous droits réservés.</span>
          <span>Propulsé par Orion ERP</span>
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
