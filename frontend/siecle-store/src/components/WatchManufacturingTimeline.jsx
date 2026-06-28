import { motion } from 'framer-motion'

const STEPS = [
  { num: '01', title: 'Design', text: 'Chaque montre naît d\'un dessin. Cadran, proportions, lignes — chaque choix est pensé pour créer une présence minimaliste et intemporelle.' },
  { num: '02', title: 'Matériaux', text: 'Acier brossé, verre trempé, cuir véritable. Chaque matière est sélectionnée pour sa durabilité, son confort et sa cohérence avec l\'identité SIÈCLE.' },
  { num: '03', title: 'Assemblage', text: 'Chaque composant est assemblé avec précision. La rigueur de l\'assemblage conditionne la finition finale et la fiabilité de la pièce.' },
  { num: '04', title: 'Contrôle', text: 'Avant d\'être proposée, chaque montre est soumise à un contrôle visuel et fonctionnel rigoureux. Aucun défaut ne passe entre les mailles.' },
  { num: '05', title: 'Présentation', text: 'La montre est conditionnée dans un écrin sobre, cohérent avec l\'univers premium de SIÈCLE — un dernier détail qui fait la différence.' },
]

export default function WatchManufacturingTimeline() {
  return (
    <section style={{ background: '#000', padding: '100px 0', overflow: 'hidden' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 24px' }}>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          style={{ marginBottom: 72 }}
        >
          <p style={{ color: '#d8c7a3', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 14 }}>
            SAVOIR-FAIRE
          </p>
          <h2 style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 'clamp(28px, 4.5vw, 52px)', fontWeight: 900,
            color: '#fff', letterSpacing: '0.02em', lineHeight: 1,
          }}>
            LA FABRICATION
          </h2>
        </motion.div>

        {/* Vertical timeline */}
        <div style={{ position: 'relative' }}>
          {/* Timeline line */}
          <motion.div
            initial={{ scaleY: 0 }}
            whileInView={{ scaleY: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1.4, ease: [0.22, 1, 0.36, 1] }}
            style={{
              position: 'absolute',
              left: 'clamp(24px, 6vw, 60px)',
              top: 0, bottom: 0, width: 1,
              background: 'linear-gradient(to bottom, #d8c7a3, rgba(216,199,163,0.1))',
              transformOrigin: 'top',
            }}
          />

          {STEPS.map((step, i) => (
            <motion.div
              key={step.num}
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ delay: i * 0.12, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              style={{
                display: 'grid',
                gridTemplateColumns: 'clamp(48px, 12vw, 120px) 1fr',
                gap: 40,
                marginBottom: 64,
                alignItems: 'flex-start',
              }}
            >
              {/* Step number with dot */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 4 }}>
                <div style={{
                  width: 14, height: 14, borderRadius: '50%',
                  background: '#d8c7a3',
                  border: '3px solid #000',
                  boxShadow: '0 0 0 2px #d8c7a3',
                  marginBottom: 10,
                  flexShrink: 0,
                  position: 'relative', zIndex: 1,
                }} />
                <span style={{
                  fontFamily: 'Montserrat, sans-serif',
                  fontSize: 'clamp(32px, 5vw, 56px)',
                  fontWeight: 900,
                  color: 'rgba(216,199,163,0.07)',
                  lineHeight: 1,
                }}>
                  {step.num}
                </span>
              </div>

              {/* Content */}
              <div style={{ paddingTop: 2 }}>
                <h3 style={{
                  fontFamily: 'Montserrat, sans-serif',
                  fontSize: 'clamp(18px, 2.5vw, 26px)',
                  fontWeight: 900, color: '#fff',
                  letterSpacing: '0.04em', textTransform: 'uppercase',
                  marginBottom: 14,
                }}>
                  {step.title}
                </h3>
                <p style={{ color: 'rgba(255,255,255,0.42)', fontSize: 14, lineHeight: 1.85, maxWidth: 540 }}>
                  {step.text}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
