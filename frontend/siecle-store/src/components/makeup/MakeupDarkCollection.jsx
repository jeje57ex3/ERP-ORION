import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'

function DarkProductComposition() {
  return (
    <svg viewBox="0 0 480 520" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="velvet" cx="50%" cy="50%" r="70%">
          <stop offset="0%"  stopColor="#1a0a05" />
          <stop offset="100%" stopColor="#0a0508" />
        </radialGradient>
        <linearGradient id="goldGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%"  stopColor="#d4a84c" />
          <stop offset="50%" stopColor="#c9a45c" />
          <stop offset="100%" stopColor="#a07830" />
        </linearGradient>
        <linearGradient id="lipGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"  stopColor="#c04858" />
          <stop offset="100%" stopColor="#8a2030" />
        </linearGradient>
        <radialGradient id="compactGrad" cx="40%" cy="40%" r="60%">
          <stop offset="0%"  stopColor="#e8c890" />
          <stop offset="100%" stopColor="#c8a060" />
        </radialGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Velvet fabric suggestion */}
      <rect width="480" height="520" fill="url(#velvet)" />
      {/* Subtle fabric texture lines */}
      {[0,1,2,3,4,5,6].map(i => (
        <line key={i} x1={i*80} y1="0" x2={i*80+40} y2="520"
          stroke="#ffffff" strokeOpacity="0.015" strokeWidth="40" />
      ))}

      {/* ── Compact powder ── */}
      <g transform="translate(60, 280)">
        <ellipse cx="75" cy="30" rx="70" ry="15" fill="#000" opacity="0.5" />
        <rect x="5" y="-60" width="140" height="80" rx="16" fill="#1a1008" stroke="#c9a45c" strokeWidth="1.2" />
        <rect x="12" y="-54" width="126" height="68" rx="12" fill="#221408" />
        <ellipse cx="75" cy="-20" rx="42" ry="36" fill="url(#compactGrad)" />
        <ellipse cx="75" cy="-20" rx="28" ry="24" fill="#d4a870" opacity="0.4" />
        <ellipse cx="68" cy="-26" rx="9" ry="7" fill="#f0d8b0" opacity="0.5" />
        {/* Gold rim */}
        <ellipse cx="75" cy="-20" rx="44" ry="38" fill="none" stroke="url(#goldGrad)" strokeWidth="1.5" />
      </g>

      {/* ── Lipstick — center ── */}
      <g transform="translate(185, 80)">
        <ellipse cx="55" cy="430" rx="28" ry="8" fill="#000" opacity="0.6" />
        {/* Tube */}
        <rect x="35" y="250" width="40" height="170" rx="8" fill="#1a0808" stroke="#8a2030" strokeWidth="1" />
        <rect x="39" y="256" width="32" height="158" rx="6" fill="#280c10" />
        {/* Cap */}
        <rect x="30" y="90" width="50" height="165" rx="6" fill="url(#lipGrad)" />
        {/* Angled bullet */}
        <path d="M30 90 Q55 50 80 90 L80 96 L30 96Z" fill="#d05868" />
        {/* Highlight */}
        <ellipse cx="50" cy="80" rx="14" ry="6" fill="#e07888" opacity="0.4" />
        {/* Gold band */}
        <rect x="30" y="240" width="50" height="16" rx="2" fill="url(#goldGrad)" opacity="0.9" />
        {/* Label line */}
        <rect x="39" y="300" width="22" height="1.5" fill="#c9a45c" opacity="0.6" />
        <rect x="39" y="314" width="16" height="1" fill="#c9a45c" opacity="0.4" />
        {/* SIÈCLE text suggestion */}
        <text x="55" y="332" fill="#c9a45c" fontSize="7" textAnchor="middle" opacity="0.7"
          fontFamily="serif" letterSpacing="2">SIÈCLE</text>
      </g>

      {/* ── Foundation bottle ── */}
      <g transform="translate(300, 150)">
        <ellipse cx="55" cy="360" rx="34" ry="10" fill="#000" opacity="0.5" />
        {/* Bottle */}
        <rect x="24" y="50" width="62" height="300" rx="12" fill="#e8d8c0" stroke="#c8b090" strokeWidth="1.2" />
        <rect x="30" y="56" width="50" height="288" rx="8" fill="#f0e4d0" />
        {/* Cap */}
        <rect x="18" y="10" width="74" height="46" rx="10" fill="#c8a870" />
        {/* Pump top */}
        <rect x="48" y="0" width="14" height="16" rx="4" fill="#c8a870" />
        <ellipse cx="55" cy="0" rx="7" ry="3" fill="#d4b880" />
        {/* Label */}
        <rect x="32" y="160" width="46" height="60" rx="4" fill="#fff" opacity="0.5" />
        <text x="55" y="188" fill="#8a6840" fontSize="6" textAnchor="middle"
          fontFamily="serif" letterSpacing="1.5">SIÈCLE</text>
        <text x="55" y="200" fill="#8a6840" fontSize="4.5" textAnchor="middle"
          letterSpacing="1">FOND DE TEINT</text>
        {/* Liquid inside — warm beige */}
        <rect x="32" y="240" width="46" height="96" rx="0 0 8 8" fill="#d4b080" opacity="0.3" />
      </g>

      {/* ── Brush ── */}
      <g transform="translate(380, 200) rotate(20, 20, 160)">
        {/* Handle */}
        <rect x="12" y="80" width="16" height="240" rx="5" fill="#2a1808" stroke="#c9a45c" strokeWidth="0.8" />
        {/* Metal ferrule */}
        <rect x="10" y="70" width="20" height="20" rx="3" fill="url(#goldGrad)" />
        {/* Bristle head */}
        <ellipse cx="20" cy="55" rx="13" ry="22" fill="#d4c0a8" />
        <ellipse cx="20" cy="48" rx="9" ry="14" fill="#e8d8c0" />
        <ellipse cx="18" cy="44" rx="4" ry="6" fill="#f0ece8" opacity="0.7" />
      </g>

      {/* Scattered rose petals suggestion */}
      <ellipse cx="120" cy="180" rx="18" ry="8" fill="#9e3a4a" opacity="0.3" transform="rotate(-30, 120, 180)" />
      <ellipse cx="380" cy="440" rx="15" ry="6" fill="#9e3a4a" opacity="0.25" transform="rotate(20, 380, 440)" />
      <ellipse cx="60" cy="440" rx="12" ry="5" fill="#c9a45c" opacity="0.2" transform="rotate(-15, 60, 440)" />

      {/* Light reflection on surface */}
      <ellipse cx="240" cy="480" rx="200" ry="15" fill="#c9a45c" opacity="0.06" filter="url(#glow)" />
    </svg>
  )
}

export default function MakeupDarkCollection() {
  return (
    <section className="makeup-dark-collection">
      {/* Content */}
      <motion.div
        className="makeup-dark-content"
        initial={{ opacity: 0, x: -40 }}
        whileInView={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        viewport={{ once: true }}
      >
        <p className="makeup-dark-kicker">Nouvelle collection</p>
        <h2 className="makeup-dark-title">
          Élégance<br />Intemporelle
        </h2>
        <p className="makeup-dark-description">
          Découvrez notre nouvelle collection aux teintes sophistiquées,
          pensées pour révéler votre beauté au quotidien.
        </p>
        <Link
          to="/boutique?categorie=maquillage&collection=elegance-intemporelle"
          className="beauty-btn beauty-btn-white"
        >
          Découvrir
        </Link>
      </motion.div>

      {/* Product visual */}
      <motion.div
        className="makeup-dark-image"
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        transition={{ duration: 1.1, delay: 0.2 }}
        viewport={{ once: true }}
      >
        <DarkProductComposition />
      </motion.div>
    </section>
  )
}
