import { motion } from 'framer-motion'

export default function ManifestoStatement({
  index = '01 / LE MANIFESTE',
  statement = "NOUS NE SUIVONS PAS LE TEMPS. NOUS L'HABILLONS.",
  text = "SIÈCLE naît du refus de la mode jetable. Chaque pièce est pensée comme un signal — une identité portée, jamais un simple vêtement. Nous travaillons la matière comme une discipline, la coupe comme une signature.",
  signature = '— MAISON SIÈCLE',
}) {
  return (
    <section style={{ padding: '120px 24px', background: 'var(--siecle-black)' }}>
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: '-100px' }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
        style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center' }}
      >
        <p style={{ color: 'var(--siecle-muted)', fontSize: 10, fontWeight: 600, letterSpacing: '0.25em', marginBottom: 28 }}>
          {index}
        </p>
        <h2 style={{
          fontFamily: 'var(--font-heading)',
          fontSize: 'clamp(28px, 4.5vw, 56px)', fontWeight: 700,
          lineHeight: 1.12, letterSpacing: '-0.01em',
          color: 'var(--siecle-white)', marginBottom: 32,
        }}>
          {statement}
        </h2>
        <p style={{ color: 'var(--siecle-muted)', fontSize: 15, lineHeight: 1.85, maxWidth: 620, margin: '0 auto 24px' }}>
          {text}
        </p>
        <p style={{ color: 'var(--siecle-beige)', fontSize: 12, fontWeight: 600, letterSpacing: '0.1em' }}>
          {signature}
        </p>
      </motion.div>
    </section>
  )
}
