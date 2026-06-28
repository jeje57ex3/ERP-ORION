import { motion } from 'framer-motion'

const ITEMS = [
  {
    label: 'Ingrédients sélectionnés',
    sub: 'Qualité premium',
    icon: (
      <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.4">
        <path d="M20 6 C20 6 10 12 10 22 C10 28 14 33 20 34 C26 33 30 28 30 22 C30 12 20 6 20 6Z" />
        <path d="M20 6 C20 6 20 18 20 34" strokeDasharray="2 3" />
        <path d="M14 16 C17 14 23 14 26 16" />
      </svg>
    ),
  },
  {
    label: 'Non testé sur les animaux',
    sub: 'Beauté éthique',
    icon: (
      <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.4">
        <circle cx="20" cy="18" r="8" />
        <ellipse cx="10" cy="11" rx="4" ry="5" />
        <ellipse cx="30" cy="11" rx="4" ry="5" />
        <path d="M14 28 Q20 35 26 28" />
        <circle cx="16" cy="17" r="1.5" fill="currentColor" stroke="none" />
        <circle cx="24" cy="17" r="1.5" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    label: 'Livraison offerte',
    sub: "Dès 80€ d'achat",
    icon: (
      <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.4">
        <rect x="4" y="14" width="24" height="16" rx="2" />
        <path d="M28 18 L34 24 L34 30 L28 30" />
        <circle cx="11" cy="32" r="3" />
        <circle cx="25" cy="32" r="3" />
        <line x1="4" y1="20" x2="28" y2="20" />
      </svg>
    ),
  },
  {
    label: 'Paiement sécurisé',
    sub: 'Transactions protégées',
    icon: (
      <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.4">
        <rect x="6" y="14" width="28" height="20" rx="3" />
        <path d="M6 20 L34 20" />
        <line x1="12" y1="27" x2="16" y2="27" />
        <line x1="20" y1="27" x2="28" y2="27" />
      </svg>
    ),
  },
]

export default function MakeupTrustBand() {
  return (
    <section className="makeup-trust-band">
      <div className="beauty-container">
        <div className="makeup-trust-grid">
          {ITEMS.map(({ label, sub, icon }, i) => (
            <motion.div
              key={label}
              className="makeup-trust-item"
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              viewport={{ once: true }}
            >
              <div className="makeup-trust-icon">{icon}</div>
              <div>
                <p className="makeup-trust-label">{label}</p>
                <p className="makeup-trust-sublabel">{sub}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
