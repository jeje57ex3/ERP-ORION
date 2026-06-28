import { motion } from 'framer-motion'
import { instagramPosts } from '../../data/makeupPlaceholders'

function InstagramIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5">
      <rect x="2" y="2" width="20" height="20" rx="5" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="17.5" cy="6.5" r="1" fill="white" stroke="none" />
    </svg>
  )
}

export default function MakeupInstagram() {
  return (
    <section className="makeup-instagram">
      <div className="beauty-container">
        <motion.div
          className="makeup-instagram-header"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          viewport={{ once: true }}
        >
          <h2 className="makeup-instagram-handle">@siecle.beauty</h2>
          <p className="makeup-instagram-sub">Rejoignez notre communauté</p>
        </motion.div>

        <div className="makeup-instagram-grid">
          {instagramPosts.map(({ id, alt, bgClass }, i) => (
            <motion.a
              key={id}
              href="https://instagram.com"
              target="_blank"
              rel="noopener noreferrer"
              className="makeup-instagram-cell"
              initial={{ opacity: 0, scale: 0.96 }}
              whileInView={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5, delay: i * 0.07 }}
              viewport={{ once: true }}
              aria-label={alt}
            >
              <div className={`makeup-instagram-cell-bg ${bgClass}`} />
              <div className="makeup-instagram-overlay">
                <span className="makeup-instagram-icon">
                  <InstagramIcon />
                </span>
              </div>
            </motion.a>
          ))}
        </div>
      </div>
    </section>
  )
}
