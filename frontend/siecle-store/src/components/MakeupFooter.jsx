import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

const LINKS = {
  Boutique: [
    { label: 'Teint', to: '/boutique?categorie=maquillage&sous-categorie=teint' },
    { label: 'Lèvres', to: '/boutique?categorie=maquillage&sous-categorie=levres' },
    { label: 'Yeux', to: '/boutique?categorie=maquillage&sous-categorie=yeux' },
    { label: 'Accessoires', to: '/boutique?categorie=maquillage&sous-categorie=accessoires' },
    { label: 'Nouveautés', to: '/boutique?categorie=maquillage&sort=-created_at' },
    { label: 'Best-sellers', to: '/boutique?categorie=maquillage&popular=true' },
  ],
  Aide: [
    { label: 'Mon compte', to: '/compte' },
    { label: 'Mes commandes', to: '/compte/commandes' },
    { label: 'Livraison & retours', to: '/aide/livraison' },
    { label: 'FAQ', to: '/aide/faq' },
    { label: 'Contact', to: '/contact' },
  ],
  Légal: [
    { label: 'Mentions légales', to: '/legal/mentions' },
    { label: 'CGV', to: '/legal/cgv' },
    { label: 'Politique de confidentialité', to: '/legal/confidentialite' },
    { label: 'Cookies', to: '/legal/cookies' },
  ],
}

export default function MakeupFooter() {
  const [newsletterEmail, setNewsletterEmail] = useState('')
  const [newsletterSent, setNewsletterSent] = useState(false)

  const handleNewsletter = async (e) => {
    e.preventDefault()
    try {
      await fetch('/api/v1/siecle/newsletter/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: newsletterEmail }),
      })
      setNewsletterSent(true)
    } catch {}
  }

  return (
    <footer style={{ background: '#090807', color: '#f7f1e8' }}>
      {/* Main footer */}
      <div style={{ maxWidth: 1320, margin: '0 auto', padding: '72px 24px 48px' }}>
        <div className="makeup-footer-grid">
          {/* Brand column */}
          <div>
            <Link to="/maquillage" style={{
              display: 'block', marginBottom: 20,
              fontFamily: 'Montserrat, sans-serif',
              fontSize: 20, fontWeight: 900,
              letterSpacing: '0.12em', color: '#f7f1e8',
              textDecoration: 'none',
            }}>
              SIÈCLE
            </Link>
            <p style={{
              fontSize: 13, lineHeight: 1.8, color: 'rgba(247,241,232,0.45)',
              maxWidth: 240, marginBottom: 28,
            }}>
              Un maquillage haut de gamme, conçu pour révéler votre allure avec élégance et précision.
            </p>
            {/* Social icons */}
            <div style={{ display: 'flex', gap: 14 }}>
              {[
                { label: 'Instagram', path: 'M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z M17.5 6.5 17.51 6.5' },
                { label: 'Pinterest', path: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14c-.55 0-1.08-.09-1.57-.24l.87-3.38c.17.08.34.14.51.19 1.84.45 3.32-.58 3.32-2.32 0-1.98-1.73-3.25-3.64-3.25-2.31 0-3.82 1.58-3.82 3.54 0 .79.24 1.49.67 2.08l-.33 1.3A8.02 8.02 0 0 1 4 12c0-4.42 3.58-8 8-8s8 3.58 8 8-3.58 8-8 8z' },
                { label: 'TikTok', path: 'M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5' },
              ].map(s => (
                <a key={s.label} href="https://instagram.com" target="_blank" rel="noopener noreferrer"
                  style={{
                    width: 36, height: 36, borderRadius: '50%',
                    border: '1px solid rgba(247,241,232,0.12)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'rgba(247,241,232,0.5)',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.borderColor = '#c9a45c'
                    e.currentTarget.style.color = '#c9a45c'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.borderColor = 'rgba(247,241,232,0.12)'
                    e.currentTarget.style.color = 'rgba(247,241,232,0.5)'
                  }}
                  title={s.label}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d={s.path}/>
                  </svg>
                </a>
              ))}
            </div>
          </div>

          {/* Link columns */}
          {Object.entries(LINKS).map(([section, links]) => (
            <div key={section}>
              <p style={{
                fontSize: 10, fontWeight: 800, letterSpacing: '0.2em',
                color: '#c9a45c', marginBottom: 20,
              }}>
                {section.toUpperCase()}
              </p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {links.map(link => (
                  <li key={link.label} style={{ marginBottom: 12 }}>
                    <Link
                      to={link.to}
                      style={{
                        fontSize: 13, color: 'rgba(247,241,232,0.45)',
                        textDecoration: 'none', transition: 'color 0.2s',
                        lineHeight: 1.5,
                      }}
                      onMouseEnter={e => { e.currentTarget.style.color = '#f7f1e8' }}
                      onMouseLeave={e => { e.currentTarget.style.color = 'rgba(247,241,232,0.45)' }}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          {/* Newsletter column */}
          <div>
            <p style={{
              fontSize: 10, fontWeight: 800, letterSpacing: '0.2em',
              color: '#c9a45c', marginBottom: 20,
            }}>
              NEWSLETTER
            </p>
            {newsletterSent ? (
              <p style={{ fontSize: 13, color: '#c9a45c', lineHeight: 1.7 }}>
                ✓ Inscription confirmée.<br />
                <span style={{ color: 'rgba(247,241,232,0.45)' }}>Merci !</span>
              </p>
            ) : (
              <>
                <p style={{ fontSize: 12, color: 'rgba(247,241,232,0.4)', lineHeight: 1.7, marginBottom: 16 }}>
                  Offres exclusives et lancements en avant-première.
                </p>
                <form onSubmit={handleNewsletter} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <input
                    type="email"
                    value={newsletterEmail}
                    onChange={e => setNewsletterEmail(e.target.value)}
                    placeholder="Votre e-mail"
                    required
                    style={{
                      padding: '12px 14px', background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(247,241,232,0.12)',
                      color: '#f7f1e8', fontSize: 13,
                      outline: 'none', fontFamily: 'Inter, sans-serif',
                    }}
                    onFocus={e => { e.target.style.borderColor = '#c9a45c' }}
                    onBlur={e => { e.target.style.borderColor = 'rgba(247,241,232,0.12)' }}
                  />
                  <button type="submit" style={{
                    padding: '12px', background: '#c9a45c', color: '#090807',
                    border: 'none', cursor: 'pointer',
                    fontSize: 11, fontWeight: 800, letterSpacing: '0.12em',
                    transition: 'opacity 0.2s',
                  }}
                    onMouseEnter={e => { e.currentTarget.style.opacity = '0.85' }}
                    onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
                  >
                    S'INSCRIRE
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div style={{
        borderTop: '1px solid rgba(247,241,232,0.06)',
        padding: '20px 24px',
      }}>
        <div style={{
          maxWidth: 1320, margin: '0 auto',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexWrap: 'wrap', gap: 12,
        }}>
          <p style={{ fontSize: 11, color: 'rgba(247,241,232,0.25)', margin: 0 }}>
            © {new Date().getFullYear()} SIÈCLE Maquillage. Tous droits réservés.
          </p>
          <p style={{ fontSize: 11, color: 'rgba(247,241,232,0.2)', margin: 0 }}>
            Cruelty-free · Vegan · Made with care
          </p>
        </div>
      </div>

      <style>{`
        .makeup-footer-grid {
          display: grid;
          grid-template-columns: 1.4fr 1fr 1fr 0.9fr 1.1fr;
          gap: 48px 32px;
        }
        @media (max-width: 1100px) {
          .makeup-footer-grid { grid-template-columns: 1fr 1fr 1fr; }
        }
        @media (max-width: 700px) {
          .makeup-footer-grid { grid-template-columns: 1fr 1fr; }
        }
        @media (max-width: 480px) {
          .makeup-footer-grid { grid-template-columns: 1fr; }
        }
      `}</style>
    </footer>
  )
}
