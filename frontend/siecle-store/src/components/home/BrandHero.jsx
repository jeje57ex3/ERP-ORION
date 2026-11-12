import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'

/* La campagne SIÈCLE. « image » est facultative : sans visuel la section
   garde son dégradé plutôt que de laisser un cadre vide. */
export default function BrandHero({ image }) {
  return (
    <section className="sh-hero" aria-label="Campagne SIÈCLE">
      {image && (
        <div className="sh-hero__media" style={{ backgroundImage: `url(${image})` }} />
      )}
      <div className="sh-hero__veil" />

      <div className="sh-wrap sh-hero__inner">
        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        >
          <p className="sh-hero__place">Paris · MMXXVI</p>
          <h1 className="sh-hero__mark">SIÈCLE</h1>
          <p className="sh-hero__claim">Une vision. Plusieurs expressions.</p>

          <div className="sh-hero__actions">
            <Link to="/boutique" className="sh-btn">
              Passer <span className="sh-link__arrow">↗</span>
            </Link>
            <Link to="/univers" className="sh-link">
              Les univers <span className="sh-link__arrow">↗</span>
            </Link>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
