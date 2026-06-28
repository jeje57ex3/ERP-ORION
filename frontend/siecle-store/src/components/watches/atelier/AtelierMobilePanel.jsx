import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import AtelierOptionDrawer from './AtelierOptionDrawer'
import AtelierStepMenu from './AtelierStepMenu'
import { SIECLE_WATCH_STEPS } from '../../../data/siecleWatchAtelierOptions'

export default function AtelierMobilePanel({ activeStep, setActiveStep, configuration, updateConfiguration, updateEngraving, onAutoSwitchBack }) {
  const [open, setOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        className="atelier-mobile-trigger"
        onClick={() => setOpen(true)}
      >
        Personnaliser — {SIECLE_WATCH_STEPS.find(s => s.key === activeStep)?.label}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="atelier-mobile-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.div
              className="atelier-mobile-sheet"
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 28, stiffness: 280 }}
            >
              <div className="atelier-mobile-sheet__handle" />
              <div className="atelier-mobile-sheet__header">
                <p className="atelier-kicker">Personnaliser</p>
                <button type="button" onClick={() => setOpen(false)} className="atelier-mobile-sheet__close">×</button>
              </div>

              <AtelierStepMenu
                steps={SIECLE_WATCH_STEPS}
                activeStep={activeStep}
                onChange={key => { setActiveStep(key) }}
              />

              <div className="atelier-mobile-sheet__content">
                <AtelierOptionDrawer
                  activeStep={activeStep}
                  configuration={configuration}
                  updateConfiguration={updateConfiguration}
                  updateEngraving={updateEngraving}
                  onAutoSwitchBack={onAutoSwitchBack}
                />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
