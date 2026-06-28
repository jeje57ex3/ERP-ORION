import { useMemo, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  SIECLE_WATCH_MODEL,
  SIECLE_WATCH_STEPS,
  SIECLE_WATCH_PRESETS,
} from '../../../data/siecleWatchAtelierOptions'
import {
  calculateAtelierPrice,
  calculateHarmonyScore,
  generateAtelierStory,
} from '../../../utils/siecleWatchAtelier'

import AtelierHeroStrip      from './AtelierHeroStrip'
import AtelierStepMenu       from './AtelierStepMenu'
import AtelierOptionDrawer   from './AtelierOptionDrawer'
import AtelierWatchStage     from './AtelierWatchStage'
import AtelierSignaturePanel from './AtelierSignaturePanel'
import AtelierPresetCarousel from './AtelierPresetCarousel'
import AtelierAddToCartBar   from './AtelierAddToCartBar'
import AtelierMobilePanel    from './AtelierMobilePanel'

const DEFAULT_CONFIGURATION = {
  caseSize:     '39mm',
  caseFinish:   'polished_steel',
  bezel:        'fluted',
  dial:         'green',
  indexes:      'baton',
  hands:        'silver',
  strap:        'jubilee_steel',
  crown:        'silver',
  glass:        'clear',
  engraving:    { enabled: false, text: '' },
  creationName: 'Ma Signature SIÈCLE',
}

export default function WatchAtelierExperience() {
  const [activeStep, setActiveStep]         = useState('silhouette')
  const [configuration, setConfiguration]   = useState(DEFAULT_CONFIGURATION)
  const [viewMode, setViewMode]             = useState('front')

  const price = useMemo(() => calculateAtelierPrice(configuration), [configuration])
  const harmonyScore = useMemo(() => calculateHarmonyScore(configuration), [configuration])
  const story = useMemo(() => generateAtelierStory(configuration), [configuration])

  const updateConfiguration = useCallback((key, value) => {
    setConfiguration(prev => ({ ...prev, [key]: value }))
  }, [])

  const updateEngraving = useCallback(value => {
    setConfiguration(prev => ({
      ...prev,
      engraving: { ...prev.engraving, ...value },
    }))
  }, [])

  const applyPreset = useCallback(preset => {
    setConfiguration({ ...preset.configuration, creationName: preset.name })
  }, [])

  return (
    <section className="atelier-experience">
      {/* Hero strip — always visible */}
      <AtelierHeroStrip model={SIECLE_WATCH_MODEL} price={price} configuration={configuration} />

      {/* Desktop layout */}
      <div className="atelier-body">
        {/* Left rail — step menu */}
        <aside className="atelier-left-rail">
          <AtelierStepMenu
            steps={SIECLE_WATCH_STEPS}
            activeStep={activeStep}
            onChange={setActiveStep}
          />
        </aside>

        {/* Options zone */}
        <motion.aside
          className="atelier-options-zone"
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        >
          <AtelierPresetCarousel presets={SIECLE_WATCH_PRESETS} onApply={applyPreset} />

          <AnimatePresence mode="wait">
            <AtelierOptionDrawer
              key={activeStep}
              activeStep={activeStep}
              configuration={configuration}
              updateConfiguration={updateConfiguration}
              updateEngraving={updateEngraving}
              onAutoSwitchBack={setViewMode}
            />
          </AnimatePresence>
        </motion.aside>

        {/* Watch stage — center */}
        <AtelierWatchStage
          configuration={configuration}
          viewMode={viewMode}
          setViewMode={setViewMode}
          activeStep={activeStep}
        />

        {/* Signature panel — right */}
        <AtelierSignaturePanel
          configuration={configuration}
          updateConfiguration={updateConfiguration}
          price={price}
          harmonyScore={harmonyScore}
          story={story}
        />
      </div>

      {/* Mobile bottom sheet trigger */}
      <div className="atelier-mobile-only">
        <AtelierMobilePanel
          activeStep={activeStep}
          setActiveStep={setActiveStep}
          configuration={configuration}
          updateConfiguration={updateConfiguration}
          updateEngraving={updateEngraving}
          onAutoSwitchBack={setViewMode}
        />
      </div>

      {/* Cart bar — bottom */}
      <AtelierAddToCartBar
        configuration={configuration}
        price={price}
        harmonyScore={harmonyScore}
      />
    </section>
  )
}
