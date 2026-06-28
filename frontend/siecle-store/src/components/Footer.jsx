import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import PoweredByOrion from './PoweredByOrion'

const COL = [
  {
    title: 'SIÈCLE',
    links: [
      { label: 'Notre histoire', to: '/maison-siecle' },
      { label: 'Boutique', to: '/boutique' },
      { label: 'Contact', to: '/contact' },
    ],
  },
  {
    title: 'MON COMPTE',
    links: [
      { label: 'Connexion', to: '/compte/connexion' },
      { label: 'Mes commandes', to: '/compte/commandes' },
      { label: 'Panier', to: '/cart' },
      { label: 'Mot de passe oublié', to: '/compte/mot-de-passe-oublie' },
    ],
  },
  {
    title: 'SERVICE',
    links: [
      { label: 'Livraison & retours', to: '/livraison-retours' },
      { label: 'FAQ', to: '/faq' },
      { label: 'Contact', to: '/contact' },
    ],
  },
  {
    title: 'LÉGAL',
    links: [
      { label: 'Mentions légales', to: '/mentions-legales' },
      { label: 'Confidentialité', to: '/confidentialite' },
      { label: 'Cookies', to: '/cookies' },
      { label: 'CGV', to: '/cgv' },
    ],
  },
]

export default function Footer() {
  return (
    <>
    <footer style={{
      background: '#0A0A0A',
      borderTop: '1px solid rgba(255,255,255,0.06)',
      padding: '64px 24px 32px',
    }}>
      <div style={{ maxWidth: 1440, margin: '0 auto' }}>
        {/* Top grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 40,
          marginBottom: 64,
        }}>
          {/* Brand col */}
          <div>
            <div style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 24, fontWeight: 900,
              letterSpacing: '0.18em', color: '#fff',
              marginBottom: 16,
            }}>
              SIÈCLE
            </div>
            <p style={{ color: 'var(--siecle-muted)', fontSize: 13, lineHeight: 1.7, maxWidth: 200 }}>
              Luxe contemporain.<br />Éditions limitées.
            </p>
          </div>

          {/* Nav cols */}
          {COL.map(col => (
            <div key={col.title}>
              <p style={{
                fontSize: 10, fontWeight: 800, letterSpacing: '0.16em',
                color: 'var(--siecle-beige)', marginBottom: 20,
              }}>
                {col.title}
              </p>
              <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {col.links.map(l => (
                  <li key={l.label}>
                    <Link to={l.to} style={{
                      color: 'var(--siecle-muted)', fontSize: 13,
                      transition: 'color 0.2s',
                    }}
                      onMouseEnter={e => e.currentTarget.style.color = '#fff'}
                      onMouseLeave={e => e.currentTarget.style.color = 'var(--siecle-muted)'}
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div style={{
          borderTop: '1px solid rgba(255,255,255,0.06)',
          paddingTop: 24,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          flexWrap: 'wrap', gap: 16,
        }}>
          <p style={{ color: 'var(--siecle-muted)', fontSize: 12 }}>
            © {new Date().getFullYear()} SIÈCLE — Tous droits réservés
          </p>
          <div style={{ display: 'flex', gap: 20 }}>
            {['Instagram', 'TikTok', 'Pinterest'].map(sn => (
              <span key={sn} style={{
                color: 'var(--siecle-muted)', fontSize: 12, cursor: 'pointer',
                transition: 'color 0.2s',
              }}
                onMouseEnter={e => e.currentTarget.style.color = '#fff'}
                onMouseLeave={e => e.currentTarget.style.color = 'var(--siecle-muted)'}
              >
                {sn}
              </span>
            ))}
          </div>
        </div>
      </div>
    </footer>
    <PoweredByOrion />
    </>
  )
}
