import { motion, AnimatePresence } from 'framer-motion'
import AtelierWatchPreview from './AtelierWatchPreview'
import AtelierViewSwitcher from './AtelierViewSwitcher'

export default function AtelierWatchStage({ configuration, viewMode, setViewMode, activeStep }) {
  const stageKey = `${activeStep}-${viewMode}-${configuration.caseFinish}-${configuration.dial}-${configuration.strap}-${configuration.hands}-${configuration.caseSize}-${configuration.bezel}-${configuration.indexes}-${configuration.engraving?.text}`

  return (
    <section className="atelier-watch-stage" aria-label="Aperçu de la montre">
      <div className="atelier-light-halo" />

      <AtelierViewSwitcher viewMode={viewMode} setViewMode={setViewMode} />

      <AnimatePresence mode="wait">
        <motion.div
          key={stageKey}
          className="atelier-watch-motion-wrap"
          initial={{ opacity: 0.7, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0.7, scale: 0.97 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
        >
          <AtelierWatchPreview configuration={configuration} viewMode={viewMode} />
        </motion.div>
      </AnimatePresence>

      <p className="atelier-stage-caption">Aperçu en direct · Chaque détail se réfléchit instantanément.</p>
    </section>
  )
}
