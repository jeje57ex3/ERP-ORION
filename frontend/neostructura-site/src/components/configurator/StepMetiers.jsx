import { METIERS } from '../../data/metiers'

export default function StepMetiers({ value, onChange, onNext }) {
  const toggle = (slug) => {
    onChange(value.includes(slug) ? value.filter(m => m !== slug) : [...value, slug])
  }

  return (
    <div>
      <h2 style={{ fontSize: 24, marginBottom: 8 }}>Quels métiers concernent votre projet ?</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 32 }}>
        Sélectionnez une ou plusieurs prestations.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }} id="neo-cfg-metiers-grid">
        {METIERS.map(m => {
          const selected = value.includes(m.slug)
          return (
            <button
              key={m.slug}
              type="button"
              onClick={() => toggle(m.slug)}
              className="neo-card"
              style={{
                padding: 24, textAlign: 'left', position: 'relative',
                borderColor: selected ? 'var(--accent)' : 'var(--border)',
                background: selected ? 'var(--bg-subtle)' : 'var(--bg-elevated)',
              }}
            >
              {selected && (
                <span style={{
                  position: 'absolute', top: 14, right: 14, width: 20, height: 20, borderRadius: '50%',
                  background: 'var(--accent)', color: 'var(--accent-contrast)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11,
                }}>✓</span>
              )}
              <div style={{ fontSize: 26, marginBottom: 10 }}>{m.icon}</div>
              <div style={{ fontSize: 14.5, fontWeight: 600 }}>{m.name}</div>
            </button>
          )
        })}
      </div>

      <div style={{ marginTop: 40, display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          className="neo-btn neo-btn-primary neo-btn-lg"
          disabled={value.length === 0}
          onClick={onNext}
          style={{ opacity: value.length === 0 ? 0.5 : 1 }}
        >
          Continuer
        </button>
      </div>

      <style>{`
        @media (max-width: 640px) { #neo-cfg-metiers-grid { grid-template-columns: repeat(2, 1fr) !important; } }
      `}</style>
    </div>
  )
}
