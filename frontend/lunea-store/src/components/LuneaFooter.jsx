import { Link } from 'react-router-dom'

const COLS = [
  {
    title: 'LUNEA',
    links: [
      { label: 'Accueil', to: '/lunea/' },
      { label: 'Boutique', to: '/lunea/boutique/' },
      { label: 'Soins', to: '/lunea/soins/' },
      { label: 'Maquillage', to: '/lunea/maquillage/' },
      { label: 'Rituels', to: '/lunea/rituels/' },
    ],
  },
  {
    title: 'MON COMPTE',
    links: [
      { label: 'Connexion', to: '/lunea/login/' },
      { label: 'Mes commandes', to: '/lunea/compte/commandes/' },
      { label: 'Fidélité', to: '/lunea/compte/fidelite/' },
      { label: 'Mot de passe oublié', to: '/lunea/mot-de-passe-oublie/' },
    ],
  },
  {
    title: 'SERVICE',
    links: [
      { label: 'Livraison & retours', to: '/lunea/livraison-retours/' },
      { label: 'FAQ', to: '/lunea/faq/' },
      { label: 'Contact', to: '/lunea/contact/' },
    ],
  },
  {
    title: 'LÉGAL',
    links: [
      { label: 'Mentions légales', to: '/lunea/mentions-legales/' },
      { label: 'Confidentialité', to: '/lunea/confidentialite/' },
      { label: 'Cookies', to: '/lunea/cookies/' },
      { label: 'CGV', to: '/lunea/cgv/' },
    ],
  },
]

export default function LuneaFooter() {
  return (
    <footer style={{
      background: '#f5ede4',
      borderTop: '1px solid rgba(201,164,92,0.18)',
      padding: '56px 24px 32px',
      color: '#3a2a1f',
    }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
          gap: 36, marginBottom: 48,
        }}>
          {/* Brand */}
          <div>
            <div style={{ fontSize: 22, fontWeight: 900, letterSpacing: '0.16em', color: '#3a2a1f', marginBottom: 12 }}>
              LUNEA
            </div>
            <p style={{ color: '#8a7878', fontSize: 13, lineHeight: 1.7, maxWidth: 180 }}>
              Beauté lumineuse,<br />douce et premium.
            </p>
          </div>

          {COLS.map(col => (
            <div key={col.title}>
              <p style={{ fontSize: 10, fontWeight: 800, letterSpacing: '0.16em', color: '#c9a45c', marginBottom: 16 }}>
                {col.title}
              </p>
              <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {col.links.map(l => (
                  <li key={l.label}>
                    <Link to={l.to} style={{ color: '#8a7878', fontSize: 13, textDecoration: 'none', transition: 'color 0.2s' }}
                      onMouseEnter={e => e.currentTarget.style.color = '#3a2a1f'}
                      onMouseLeave={e => e.currentTarget.style.color = '#8a7878'}
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div style={{
          borderTop: '1px solid rgba(201,164,92,0.18)', paddingTop: 20,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          flexWrap: 'wrap', gap: 12,
        }}>
          <p style={{ color: '#b8a89a', fontSize: 12 }}>© {new Date().getFullYear()} LUNEA — Tous droits réservés</p>
          <p style={{ color: '#b8a89a', fontSize: 11, letterSpacing: '0.1em' }}>Propulsé par Orion ERP</p>
        </div>
      </div>
    </footer>
  )
}
