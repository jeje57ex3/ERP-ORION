import { motion } from 'framer-motion'

const ITEMS = [
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M5 12h14M12 5l7 7-7 7"/>
      </svg>
    ),
    label: 'Livraison Europe',
    sub: 'Offerte dès 50€',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
      </svg>
    ),
    label: 'Maison indépendante',
    sub: 'Production limitée',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
      </svg>
    ),
    label: 'Service client',
    sub: 'Réponse sous 24h',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
        <line x1="1" y1="10" x2="23" y2="10"/>
      </svg>
    ),
    label: 'Paiement sécurisé',
    sub: 'Stripe & 3D Secure',
  },
]

export default function TrustBand() {
  return (
    <motion.section
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true }}
      style={{
        background: 'var(--siecle-black)',
        borderTop: '1px solid var(--siecle-border)',
        borderBottom: '1px solid var(--siecle-border)',
        padding: '0',
      }}
    >
      <div style={{
        maxWidth: 1320, margin: '0 auto', padding: '0 24px',
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
      }}
        className="trust-band-grid"
      >
        {ITEMS.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.08 }}
            style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '22px 24px',
              borderRight: i < 3 ? '1px solid var(--siecle-border)' : 'none',
            }}
          >
            <span style={{ color: 'var(--siecle-beige)', flexShrink: 0 }}>{item.icon}</span>
            <div>
              <p style={{ fontSize: 12, fontWeight: 700, color: 'var(--siecle-white)', margin: 0, letterSpacing: '0.04em' }}>
                {item.label}
              </p>
              <p style={{ fontSize: 11, color: 'var(--siecle-muted)', margin: '2px 0 0' }}>
                {item.sub}
              </p>
            </div>
          </motion.div>
        ))}
      </div>

      <style>{`
        @media (max-width: 768px) {
          .trust-band-grid { grid-template-columns: 1fr 1fr !important; }
          .trust-band-grid > div { border-right: none !important; border-bottom: 1px solid var(--siecle-border); }
        }
        @media (max-width: 480px) {
          .trust-band-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </motion.section>
  )
}
