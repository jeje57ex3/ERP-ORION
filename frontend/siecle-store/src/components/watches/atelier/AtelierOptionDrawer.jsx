import { motion } from 'framer-motion'
import { SIECLE_WATCH_OPTIONS, SIECLE_WATCH_STEPS } from '../../../data/siecleWatchAtelierOptions'
import AtelierOptionGroup from './AtelierOptionGroup'
import AtelierEngravingPanel from './AtelierEngravingPanel'

export default function AtelierOptionDrawer({
  activeStep,
  configuration,
  updateConfiguration,
  updateEngraving,
  onAutoSwitchBack,
}) {
  const step = SIECLE_WATCH_STEPS.find(s => s.key === activeStep)
  const groups = SIECLE_WATCH_OPTIONS[activeStep] || []

  if (activeStep === 'signature') {
    return (
      <motion.div
        className="atelier-option-drawer"
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -18 }}
        transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="atelier-option-heading">
          <p>Étape 7</p>
          <h2>Votre signature</h2>
          <span>Consultez le panneau de droite pour finaliser et ajouter au panier.</span>
        </div>
      </motion.div>
    )
  }

  return (
    <motion.div
      className="atelier-option-drawer"
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -18 }}
      transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="atelier-option-heading">
        <p>{step?.label}</p>
        <h2>{step?.title}</h2>
        <span>{step?.description}</span>
      </div>

      <div className="atelier-option-groups">
        {groups.map(group => {
          if (group.type === 'engraving') {
            return (
              <AtelierEngravingPanel
                key={group.key}
                group={group}
                engraving={configuration.engraving}
                updateEngraving={updateEngraving}
                onAutoSwitchBack={onAutoSwitchBack}
              />
            )
          }
          return (
            <AtelierOptionGroup
              key={group.key}
              group={group}
              selectedValue={configuration[group.key]}
              onChange={value => updateConfiguration(group.key, value)}
            />
          )
        })}
      </div>
    </motion.div>
  )
}
