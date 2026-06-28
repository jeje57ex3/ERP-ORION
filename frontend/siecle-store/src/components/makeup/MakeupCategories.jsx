import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { makeupCategories } from '../../data/makeupProducts'

const cardVariants = {
  hidden: { opacity: 0, y: 32 },
  show: i => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.65, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] },
  }),
}

export default function MakeupCategories() {
  return (
    <section className="makeup-categories">
      <div className="beauty-container">
        <motion.h2
          className="beauty-section-title"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          viewport={{ once: true }}
        >
          Nos Univers
        </motion.h2>
        <span className="beauty-section-rule" />

        <div className="makeup-categories-grid">
          {makeupCategories.map(({ id, label, subtitle, href, bgClass }, i) => (
            <motion.div
              key={id}
              custom={i}
              variants={cardVariants}
              initial="hidden"
              whileInView="show"
              viewport={{ once: true }}
            >
              <Link to={href} className="makeup-category-card">
                <div className={`makeup-category-bg ${bgClass}`} />
                <div className="makeup-category-overlay" />
                <div className="makeup-category-body">
                  <p className="makeup-category-name">{label}</p>
                  <p className="makeup-category-subtitle">{subtitle}</p>
                  <span className="makeup-category-link">Découvrir</span>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
