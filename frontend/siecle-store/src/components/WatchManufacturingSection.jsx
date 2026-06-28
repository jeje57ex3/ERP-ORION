import { motion } from 'framer-motion'

const STEPS = [
  {
    num: '01',
    title: 'Design',
    text: 'Chaque montre commence par une silhouette. Le cadran, les proportions et les lignes sont dessinés pour créer une présence minimaliste et intemporelle.',
  },
  {
    num: '02',
    title: 'Matériaux',
    text: 'Nous privilégions des matériaux robustes, élégants et confortables : acier, finitions sombres, touches argentées ou beige, verre résistant et bracelets adaptés au quotidien.',
  },
  {
    num: '03',
    title: 'Assemblage',
    text: 'Chaque composant est assemblé avec précision pour garantir un rendu propre, solide et cohérent avec l\'identité SIÈCLE.',
  },
  {
    num: '04',
    title: 'Contrôle',
    text: 'Avant d\'être proposée à la vente, chaque montre passe par un contrôle visuel et fonctionnel afin de vérifier la finition, le confort et la fiabilité.',
  },
  {
    num: '05',
    title: 'Présentation',
    text: 'La montre est ensuite préparée dans un packaging sobre, fidèle à l\'univers premium et minimaliste de SIÈCLE.',
  },
]

export default function WatchManufacturingSection() {
  return (
    <section id="fabrication" style={{ padding: '100px 24px', background: '#050505' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          style={{ textAlign: 'center', marginBottom: 80 }}
        >
          <p style={{ color: '#C0A882', fontSize: 9, fontWeight: 800, letterSpacing: '0.28em', marginBottom: 14 }}>
            SAVOIR-FAIRE
          </p>
          <h2 style={{
            fontFamily: 'Montserrat, sans-serif',
            fontSize: 'clamp(28px, 4.5vw, 52px)', fontWeight: 900,
            color: '#fff', letterSpacing: '0.02em',
          }}>
            LA FABRICATION
          </h2>
        </motion.div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {STEPS.map((step, i) => (
            <motion.div
              key={step.num}
              initial={{ opacity: 0, x: i % 2 === 0 ? -24 : 24 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ delay: 0.1, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              style={{
                display: 'grid',
                gridTemplateColumns: i % 2 === 0 ? '1fr 3fr' : '3fr 1fr',
                gap: 0,
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                padding: '52px 0',
                alignItems: 'center',
              }}
              className="watch-step"
            >
              {i % 2 === 0 ? (
                <>
                  <div style={{ paddingRight: 48 }}>
                    <span style={{
                      fontFamily: 'Montserrat, sans-serif',
                      fontSize: 'clamp(52px, 8vw, 100px)',
                      fontWeight: 900,
                      color: 'rgba(192,168,130,0.08)',
                      lineHeight: 1,
                      display: 'block',
                    }}>
                      {step.num}
                    </span>
                  </div>
                  <div>
                    <p style={{ color: '#C0A882', fontSize: 9, fontWeight: 800, letterSpacing: '0.22em', marginBottom: 12 }}>
                      ÉTAPE {step.num}
                    </p>
                    <h3 style={{
                      fontFamily: 'Montserrat, sans-serif',
                      fontSize: 'clamp(20px, 3vw, 30px)', fontWeight: 900,
                      color: '#fff', letterSpacing: '0.04em',
                      textTransform: 'uppercase', marginBottom: 16,
                    }}>
                      {step.title}
                    </h3>
                    <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, lineHeight: 1.85, maxWidth: 520 }}>
                      {step.text}
                    </p>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ textAlign: 'right', paddingRight: 0 }}>
                    <p style={{ color: '#C0A882', fontSize: 9, fontWeight: 800, letterSpacing: '0.22em', marginBottom: 12 }}>
                      ÉTAPE {step.num}
                    </p>
                    <h3 style={{
                      fontFamily: 'Montserrat, sans-serif',
                      fontSize: 'clamp(20px, 3vw, 30px)', fontWeight: 900,
                      color: '#fff', letterSpacing: '0.04em',
                      textTransform: 'uppercase', marginBottom: 16,
                    }}>
                      {step.title}
                    </h3>
                    <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, lineHeight: 1.85, maxWidth: 520, marginLeft: 'auto' }}>
                      {step.text}
                    </p>
                  </div>
                  <div style={{ paddingLeft: 48, textAlign: 'right' }}>
                    <span style={{
                      fontFamily: 'Montserrat, sans-serif',
                      fontSize: 'clamp(52px, 8vw, 100px)',
                      fontWeight: 900,
                      color: 'rgba(192,168,130,0.08)',
                      lineHeight: 1,
                      display: 'block',
                    }}>
                      {step.num}
                    </span>
                  </div>
                </>
              )}
            </motion.div>
          ))}
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .watch-step { grid-template-columns: 1fr !important; gap: 12px !important; }
        }
      `}</style>
    </section>
  )
}
