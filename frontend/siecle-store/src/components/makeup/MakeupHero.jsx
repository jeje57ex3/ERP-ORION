import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'

function HeroFacePlaceholder() {
  return (
    <div className="makeup-hero-placeholder">
      <svg viewBox="0 0 600 800" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <radialGradient id="skinBase" cx="50%" cy="38%" r="55%">
            <stop offset="0%"  stopColor="#d4b5a0" />
            <stop offset="60%" stopColor="#c8a48c" />
            <stop offset="100%" stopColor="#b08870" />
          </radialGradient>
          <radialGradient id="blush" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#d4908a" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#d4908a" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="glow" cx="50%" cy="20%" r="60%">
            <stop offset="0%"  stopColor="#e8d0bc" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#c8a48c" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"  stopColor="#dfd0c0" />
            <stop offset="100%" stopColor="#c4a080" />
          </linearGradient>
        </defs>

        {/* Background */}
        <rect width="600" height="800" fill="url(#bgGrad)" />

        {/* Neck / shoulders suggestion */}
        <ellipse cx="300" cy="820" rx="180" ry="160" fill="url(#skinBase)" />
        <ellipse cx="300" cy="720" rx="80"  ry="120" fill="url(#skinBase)" />

        {/* Face oval */}
        <ellipse cx="300" cy="370" rx="155" ry="195" fill="url(#skinBase)" />

        {/* Highlight glow */}
        <ellipse cx="300" cy="310" rx="80" ry="90" fill="url(#glow)" />

        {/* Eye shadow — left */}
        <ellipse cx="238" cy="348" rx="34" ry="14" fill="#8B4A3A" opacity="0.5" />
        {/* Eye — left */}
        <ellipse cx="238" cy="352" rx="28" ry="11" fill="#1a0a08" />
        <ellipse cx="235" cy="349" rx="9"  ry="7"  fill="#3a2820" />
        <circle  cx="233" cy="348" r="3.5" fill="#050505" />
        <circle  cx="232" cy="347" r="1.2" fill="#ffffff" opacity="0.9" />
        {/* Lash line */}
        <path d="M210 349 Q238 340 266 349" fill="none" stroke="#050505" strokeWidth="1.8" />

        {/* Eye shadow — right */}
        <ellipse cx="362" cy="348" rx="34" ry="14" fill="#8B4A3A" opacity="0.5" />
        {/* Eye — right */}
        <ellipse cx="362" cy="352" rx="28" ry="11" fill="#1a0a08" />
        <ellipse cx="365" cy="349" rx="9"  ry="7"  fill="#3a2820" />
        <circle  cx="367" cy="348" r="3.5" fill="#050505" />
        <circle  cx="368" cy="347" r="1.2" fill="#ffffff" opacity="0.9" />
        <path d="M334 349 Q362 340 390 349" fill="none" stroke="#050505" strokeWidth="1.8" />

        {/* Brows */}
        <path d="M208 325 Q238 312 268 318" fill="none" stroke="#3a2010" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M332 318 Q362 312 392 325" fill="none" stroke="#3a2010" strokeWidth="2.2" strokeLinecap="round" />

        {/* Nose */}
        <path d="M293 370 Q288 408 275 418 Q296 426 325 418 Q312 408 307 370" fill="none" stroke="#c09080" strokeWidth="1.2" opacity="0.5" />

        {/* Lips — upper */}
        <path d="M265 455 Q278 447 300 451 Q322 447 335 455 Q322 460 300 458 Q278 460 265 455Z" fill="#9e3a4a" />
        {/* Lips — lower */}
        <path d="M265 455 Q278 460 300 458 Q322 460 335 455 Q325 475 300 478 Q275 475 265 455Z" fill="#c04858" />
        {/* Lip highlight */}
        <ellipse cx="300" cy="467" rx="18" ry="5" fill="#d06070" opacity="0.4" />

        {/* Blush cheeks */}
        <ellipse cx="200" cy="400" rx="55" ry="30" fill="url(#blush)" />
        <ellipse cx="400" cy="400" rx="55" ry="30" fill="url(#blush)" />

        {/* Hair suggestion — top + sides */}
        <ellipse cx="300" cy="195" rx="165" ry="120" fill="#1a0e08" />
        <ellipse cx="155" cy="370" rx="40" ry="180" fill="#1a0e08" />
        <ellipse cx="445" cy="370" rx="40" ry="180" fill="#1a0e08" />
        {/* Hair ear reveal */}
        <ellipse cx="300" cy="178" rx="145" ry="95" fill="url(#skinBase)" opacity="0.15" />

        {/* Ears */}
        <ellipse cx="148" cy="390" rx="16" ry="22" fill="url(#skinBase)" />
        <ellipse cx="452" cy="390" rx="16" ry="22" fill="url(#skinBase)" />

        {/* Earring — subtle gold dot */}
        <circle cx="148" cy="410" r="5"  fill="#c9a45c" opacity="0.85" />
        <circle cx="452" cy="410" r="5"  fill="#c9a45c" opacity="0.85" />

        {/* Skin highlight — bridge of nose and cheekbones */}
        <ellipse cx="300" cy="355" rx="12" ry="40" fill="#e8d0bc" opacity="0.3" />
        <ellipse cx="228" cy="375" rx="22" ry="14" fill="#e8d0bc" opacity="0.25" />
        <ellipse cx="372" cy="375" rx="22" ry="14" fill="#e8d0bc" opacity="0.25" />
      </svg>
    </div>
  )
}

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.15, delayChildren: 0.1 } },
}
const itemVariants = {
  hidden: { opacity: 0, y: 40 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] } },
}

export default function MakeupHero() {
  return (
    <section className="makeup-hero">
      {/* Content */}
      <motion.div
        className="makeup-hero-content"
        variants={containerVariants}
        initial="hidden"
        animate="show"
      >
        <motion.p className="makeup-hero-kicker" variants={itemVariants}>
          Révélez votre éclat
        </motion.p>
        <motion.h1 className="makeup-hero-title" variants={itemVariants}>
          L'Art du<br />Maquillage
        </motion.h1>
        <motion.p className="makeup-hero-description" variants={itemVariants}>
          Des produits haute qualité pour sublimer votre beauté naturelle.
        </motion.p>
        <motion.div variants={itemVariants}>
          <Link to="/boutique?categorie=maquillage" className="beauty-btn">
            Découvrir la collection
          </Link>
        </motion.div>
      </motion.div>

      {/* Image */}
      <motion.div
        className="makeup-hero-image"
        initial={{ opacity: 0, scale: 1.04 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
      >
        <HeroFacePlaceholder />
      </motion.div>
    </section>
  )
}
