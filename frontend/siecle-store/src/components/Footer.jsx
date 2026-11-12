import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import PoweredByOrion from './PoweredByOrion'

/* Les colonnes du pied, reprises du site de reference : « LE VESTIAIRE »,
   « AIDE & SERVICES », « INFORMATIONS ». La colonne « LÉGAL » est CONSERVÉE
   bien qu'absente de la reference : mentions legales, CGV, cookies et
   confidentialite sont obligatoires, et les perdre au nom du dessin serait
   une faute. */
const COL = [
  {
    title: 'LE VESTIAIRE',
    links: [
      { label: 'Streetwear', to: '/vetements' },
      { label: 'Costumes italiens', to: '/vetements?categorie=tailleur' },
      { label: 'Montres', to: '/montres' },
      { label: 'Accessoires', to: '/boutique?category=accessoires' },
    ],
  },
  {
    title: 'AIDE & SERVICES',
    links: [
      { label: 'Contact', to: '/contact' },
      { label: 'Livraison & retours', to: '/livraison-retours' },
      { label: 'Guide des tailles', to: '/guide-taille' },
      { label: 'FAQ', to: '/faq' },
    ],
  },
  {
    title: 'INFORMATIONS',
    links: [
      { label: 'Notre histoire', to: '/maison-siecle' },
      { label: 'Mon compte', to: '/compte/connexion' },
      { label: 'Mes commandes', to: '/compte/commandes' },
      { label: 'Mon panier', to: '/cart' },
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
      borderTop: '1px solid rgba(241,237,229,0.06)',
      padding: '64px 24px 32px',
    }}>
      <div style={{ maxWidth: 1440, margin: '0 auto' }}>

        {/* Bloc de marque, repris du site de reference. */}
        <div style={{
          borderBottom: '1px solid rgba(241,237,229,0.06)',
          paddingBottom: 56,
          marginBottom: 56,
        }}>
          <p style={{
            fontSize: 10, fontWeight: 600, letterSpacing: '0.3em',
            textTransform: 'uppercase', color: 'var(--siecle-muted)', margin: 0,
          }}>
            Siècle / Paris
          </p>
          <p style={{
            fontSize: 11, fontWeight: 700, letterSpacing: '0.22em',
            textTransform: 'uppercase', color: 'var(--siecle-gold)',
            margin: '14px 0 0',
          }}>
            Plus qu’une marque, un siècle d’avance.
          </p>

          <p style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 'clamp(44px, 9vw, 132px)', fontWeight: 700,
            lineHeight: 0.96, letterSpacing: '-0.02em',
            color: 'var(--siecle-white)', margin: '24px 0 0',
          }}>
            SIÈCLE<span style={{ color: 'var(--siecle-gold)' }}>.</span>
          </p>

          <p style={{
            fontSize: 15, lineHeight: 1.8, color: 'var(--siecle-muted-soft)',
            margin: '22px 0 0', maxWidth: '44ch',
          }}>
            Une vision. Plusieurs expressions.<br />
            Des pièces choisies pour affirmer ton style.
          </p>

          <Link
            to="/boutique"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 10,
              marginTop: 34, paddingBottom: 6,
              borderBottom: '1px solid var(--siecle-line)',
              fontSize: 11, fontWeight: 700, letterSpacing: '0.18em',
              textTransform: 'uppercase', color: 'var(--siecle-white)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.color = 'var(--siecle-beige)'
              e.currentTarget.style.borderBottomColor = 'var(--siecle-beige)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.color = 'var(--siecle-white)'
              e.currentTarget.style.borderBottomColor = 'var(--siecle-line)'
            }}
          >
            Explorer le vestiaire <span>↗</span>
          </Link>
        </div>

        {/* Top grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 40,
          marginBottom: 64,
        }}>
          {/* Le nom est deja pose en grand juste au-dessus : la colonne
              porte desormais la signature de la marque. */}
          <div>
            <p style={{
              fontSize: 10, fontWeight: 700, letterSpacing: '0.22em',
              textTransform: 'uppercase', color: 'var(--siecle-white)',
              marginBottom: 14,
            }}>
              Conçu pour durer.
            </p>
            <p style={{ color: 'var(--siecle-muted)', fontSize: 13, lineHeight: 1.7, maxWidth: 200 }}>
              Porté à ta façon.<br />Paris · MMXXVI.
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
                      onMouseEnter={e => e.currentTarget.style.color = 'var(--siecle-white)'}
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
          borderTop: '1px solid rgba(241,237,229,0.06)',
          paddingTop: 24,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          flexWrap: 'wrap', gap: 16,
        }}>
          <div>
            <p style={{ color: 'var(--siecle-muted)', fontSize: 12 }}>
              © {new Date().getFullYear()} SIÈCLE. Tous droits réservés.
            </p>
            <p style={{ color: 'var(--siecle-muted)', fontSize: 10, letterSpacing: '0.2em', textTransform: 'uppercase', marginTop: 6 }}>
              Conçu pour durer. Porté à ta façon.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
            <button
              type="button"
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              style={{
                background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                color: 'var(--siecle-muted)', fontSize: 11, fontWeight: 700,
                letterSpacing: '0.16em', textTransform: 'uppercase',
              }}
              onMouseEnter={e => { e.currentTarget.style.color = 'var(--siecle-white)' }}
              onMouseLeave={e => { e.currentTarget.style.color = 'var(--siecle-muted)' }}
            >
              Retour en haut ↑
            </button>
            {['Instagram', 'TikTok', 'Pinterest'].map(sn => (
              <span key={sn} style={{
                color: 'var(--siecle-muted)', fontSize: 12, cursor: 'pointer',
                transition: 'color 0.2s',
              }}
                onMouseEnter={e => e.currentTarget.style.color = 'var(--siecle-white)'}
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
