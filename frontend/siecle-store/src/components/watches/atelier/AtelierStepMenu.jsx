export default function AtelierStepMenu({ steps, activeStep, onChange }) {
  return (
    <nav className="atelier-step-menu" aria-label="Étapes de personnalisation">
      {steps.map((step, index) => (
        <button
          key={step.key}
          type="button"
          className={`atelier-step-button${activeStep === step.key ? ' is-active' : ''}`}
          onClick={() => onChange(step.key)}
          title={step.title}
        >
          <span className="atelier-step-number">{String(index + 1).padStart(2, '0')}</span>
          <span>{step.label}</span>
        </button>
      ))}
    </nav>
  )
}
