import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { watchAnatomy } from '../data/watchAnatomy'
import WatchHotspot from './WatchHotspot'
import '../styles/watches.css'

// SVG watch illustration
function WatchSVG() {
  return (
    <svg viewBox="0 0 200 364" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Top strap */}
      <rect x="66" y="4" width="68" height="72" rx="8" fill="#1C1C1C"/>
      <line x1="80" y1="14" x2="80" y2="70" stroke="#252525" strokeWidth="1"/>
      <line x1="90" y1="14" x2="90" y2="70" stroke="#252525" strokeWidth="1"/>
      <circle cx="100" cy="30" r="3" fill="#111"/>
      <circle cx="100" cy="44" r="3" fill="#111"/>
      <circle cx="100" cy="58" r="3" fill="#111"/>

      {/* Top lugs */}
      <path d="M66 68 Q46 68 40 82" stroke="#1C1C1C" strokeWidth="16" fill="none" strokeLinecap="round"/>
      <path d="M134 68 Q154 68 160 82" stroke="#1C1C1C" strokeWidth="16" fill="none" strokeLinecap="round"/>

      {/* Watch case outer */}
      <rect x="28" y="74" width="144" height="192" rx="34" fill="#1A1A1A"/>
      {/* Case inner bezel */}
      <rect x="31" y="77" width="138" height="186" rx="31" fill="#111" stroke="#2E2E2E" strokeWidth="1"/>
      {/* Brushed surface hint */}
      <rect x="34" y="80" width="132" height="180" rx="28" fill="#0D0D0D" stroke="#222" strokeWidth="0.5"/>

      {/* Dial */}
      <circle cx="100" cy="170" r="72" fill="#080808" stroke="#1E1E1E" strokeWidth="2"/>
      <circle cx="100" cy="170" r="66" fill="none" stroke="#161616" strokeWidth="0.5"/>

      {/* Hour indices */}
      <rect x="97" y="103" width="6" height="15" rx="2" fill="#AFAFAF"/>
      <rect x="157" y="167" width="15" height="6" rx="2" fill="#AFAFAF"/>
      <rect x="97" y="222" width="6" height="15" rx="2" fill="#AFAFAF"/>
      <rect x="28" y="167" width="15" height="6" rx="2" fill="#AFAFAF"/>

      {/* Minor markers */}
      <circle cx="100" cy="107" r="1.5" fill="#3A3A3A"/>
      <circle cx="131" cy="114" r="1.5" fill="#3A3A3A"/>
      <circle cx="153" cy="137" r="1.5" fill="#3A3A3A"/>
      <circle cx="153" cy="199" r="1.5" fill="#3A3A3A"/>
      <circle cx="131" cy="222" r="1.5" fill="#3A3A3A"/>
      <circle cx="69" cy="222" r="1.5" fill="#3A3A3A"/>
      <circle cx="47" cy="199" r="1.5" fill="#3A3A3A"/>
      <circle cx="47" cy="137" r="1.5" fill="#3A3A3A"/>
      <circle cx="69" cy="114" r="1.5" fill="#3A3A3A"/>

      {/* Brand text */}
      <text x="100" y="152" textAnchor="middle" fill="#888888" fontSize="7" letterSpacing="3.5" fontFamily="sans-serif">SIÈCLE</text>
      <line x1="80" y1="158" x2="120" y2="158" stroke="#2A2A2A" strokeWidth="0.5"/>
      <text x="100" y="192" textAnchor="middle" fill="#444" fontSize="5" fontFamily="sans-serif" letterSpacing="2">AUTOMATIC</text>

      {/* Hour hand (10h10 position) */}
      <line x1="100" y1="170" x2="75" y2="127" stroke="#D8C7A3" strokeWidth="4" strokeLinecap="round"/>
      {/* Minute hand */}
      <line x1="100" y1="170" x2="125" y2="112" stroke="#D8C7A3" strokeWidth="2.5" strokeLinecap="round"/>
      {/* Second hand */}
      <line x1="100" y1="182" x2="100" y2="108" stroke="#8B7355" strokeWidth="1" strokeLinecap="round"/>

      {/* Center cap */}
      <circle cx="100" cy="170" r="6" fill="#D8C7A3"/>
      <circle cx="100" cy="170" r="3.5" fill="#0A0A0A"/>

      {/* Crown */}
      <rect x="170" y="158" width="22" height="24" rx="5" fill="#242424" stroke="#3C3C3C" strokeWidth="1"/>
      <line x1="175" y1="163" x2="175" y2="177" stroke="#404040" strokeWidth="1.2"/>
      <line x1="180" y1="163" x2="180" y2="177" stroke="#404040" strokeWidth="1.2"/>
      <line x1="185" y1="163" x2="185" y2="177" stroke="#404040" strokeWidth="1.2"/>

      {/* Bottom lugs */}
      <path d="M66 266 Q46 272 40 282" stroke="#1C1C1C" strokeWidth="16" fill="none" strokeLinecap="round"/>
      <path d="M134 266 Q154 272 160 282" stroke="#1C1C1C" strokeWidth="16" fill="none" strokeLinecap="round"/>

      {/* Bottom strap */}
      <rect x="66" y="262" width="68" height="90" rx="8" fill="#1C1C1C"/>
      <line x1="80" y1="272" x2="80" y2="344" stroke="#252525" strokeWidth="1"/>
      <line x1="90" y1="272" x2="90" y2="344" stroke="#252525" strokeWidth="1"/>
      <circle cx="100" cy="290" r="3" fill="#111"/>
      <circle cx="100" cy="306" r="3" fill="#111"/>
      <circle cx="100" cy="322" r="3" fill="#111"/>

      {/* Clasp */}
      <rect x="74" y="336" width="52" height="22" rx="4" fill="#1E1E1E" stroke="#383838" strokeWidth="1"/>
      <rect x="80" y="340" width="40" height="2" rx="1" fill="#303030"/>
      <rect x="80" y="348" width="40" height="2" rx="1" fill="#303030"/>
      <rect x="96" y="335" width="8" height="24" rx="2" fill="#242424" stroke="#333" strokeWidth="0.5"/>
    </svg>
  )
}

// Partition: left-side parts (show in left panel) vs right-side parts
const LEFT_PARTS = ['case', 'movement', 'glass']
const RIGHT_PARTS = ['crown', 'hands', 'finish']
const CENTER_PARTS = ['dial', 'strap', 'clasp']

export default function WatchAnatomyAnimation() {
  const [activeId, setActiveId] = useState('dial')
  const [mobileOpen, setMobileOpen] = useState(null)
  const activePart = watchAnatomy.find(p => p.id === activeId)

  const handleActivate = (id) => setActiveId(id)

  const leftParts = watchAnatomy.filter(p => LEFT_PARTS.includes(p.id))
  const rightParts = watchAnatomy.filter(p => RIGHT_PARTS.includes(p.id))
  const centerParts = watchAnatomy.filter(p => CENTER_PARTS.includes(p.id))

  return (
    <section className="watch-anatomy-section" id="anatomie">
      <div className="watch-anatomy-wrapper">
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ color: '#d8c7a3', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 16 }}
        >
          ANATOMIE
        </motion.p>
        <motion.h2
          className="watch-anatomy-title"
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          style={{ fontFamily: 'Montserrat, sans-serif' }}
        >
          La montre<br />dans le détail.
        </motion.h2>
        <motion.p
          className="watch-anatomy-intro"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.25 }}
        >
          Chaque composant est pensé pour servir l'identité de la pièce. Survolez ou cliquez sur un point pour découvrir le détail correspondant.
        </motion.p>

        {/* Desktop layout */}
        <div className="watch-anatomy-stage">
          {/* Left panel */}
          <div className="watch-anatomy-panel watch-anatomy-panel-left">
            {[...leftParts, ...centerParts.slice(0, 1)].map((part, i) => (
              <motion.div
                key={part.id}
                className={`watch-description-card${activeId === part.id ? ' active' : ''}`}
                onClick={() => handleActivate(part.id)}
                onMouseEnter={() => handleActivate(part.id)}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.4 + i * 0.1 }}
                style={{ textAlign: 'right' }}
              >
                <span className="watch-hotspot-label">{part.label}</span>
                <h3>{part.title}</h3>
                <AnimatePresence>
                  {activeId === part.id && (
                    <motion.p
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.3 }}
                    >
                      {part.description}
                    </motion.p>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>

          {/* Watch visual with hotspots */}
          <motion.div
            className="watch-visual"
            initial={{ opacity: 0, scale: 0.92 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ delay: 0.3, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          >
            <WatchSVG />
            {watchAnatomy.map((part, i) => (
              <WatchHotspot
                key={part.id}
                part={part}
                index={i}
                isActive={activeId === part.id}
                onActivate={handleActivate}
              />
            ))}
          </motion.div>

          {/* Right panel */}
          <div className="watch-anatomy-panel watch-anatomy-panel-right">
            {[...rightParts, ...centerParts.slice(1)].map((part, i) => (
              <motion.div
                key={part.id}
                className={`watch-description-card${activeId === part.id ? ' active' : ''}`}
                onClick={() => handleActivate(part.id)}
                onMouseEnter={() => handleActivate(part.id)}
                initial={{ opacity: 0, x: 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.4 + i * 0.1 }}
              >
                <span className="watch-hotspot-label">{part.label}</span>
                <h3>{part.title}</h3>
                <AnimatePresence>
                  {activeId === part.id && (
                    <motion.p
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.3 }}
                    >
                      {part.description}
                    </motion.p>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Mobile accordion */}
        <div className="watch-mobile-list">
          {watchAnatomy.map((part, i) => (
            <motion.div
              key={part.id}
              className="watch-mobile-item"
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.05 }}
            >
              <button
                className="watch-mobile-item-header"
                onClick={() => setMobileOpen(mobileOpen === part.id ? null : part.id)}
              >
                <h4>{part.title}</h4>
                <span style={{ color: '#d8c7a3', fontSize: 18, fontWeight: 300 }}>
                  {mobileOpen === part.id ? '−' : '+'}
                </span>
              </button>
              <AnimatePresence>
                {mobileOpen === part.id && (
                  <motion.div
                    className="watch-mobile-item-content"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    {part.description}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
