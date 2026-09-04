const INTERVENTIONS = [
  { value: 'installation_neuve', label: 'Installation neuve', icon: '🆕' },
  { value: 'renovation', label: 'Rénovation', icon: '🔄' },
  { value: 'depannage', label: 'Dépannage', icon: '⚠️' },
  { value: 'mise_normes', label: 'Mise aux normes', icon: '📐' },
  { value: 'autre', label: "Ajout d'équipements", icon: '➕' },
]

const URGENCIES = [
  { value: 'urgent', label: 'Urgent', desc: 'Sous 48h' },
  { value: 'normal', label: 'Normal', desc: 'Sous 2 semaines' },
  { value: 'flexible', label: 'Flexible', desc: "Pas de contrainte" },
]

export default function StepIntervention({ intervention, urgency, onChangeIntervention, onChangeUrgency, onNext, onBack }) {
  return (
    <div>
      <h2 style={{ fontSize: 24, marginBottom: 8 }}>Quel type d'intervention ?</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 32 }}>
        Précisez la nature des travaux et l'urgence.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 36 }} id="neo-cfg-interv-grid">
        {INTERVENTIONS.map(opt => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChangeIntervention(opt.value)}
            className="neo-card"
            style={{
              padding: 20, textAlign: 'left',
              borderColor: intervention === opt.value ? 'var(--accent)' : 'var(--border)',
              background: intervention === opt.value ? 'var(--bg-subtle)' : 'var(--bg-elevated)',
            }}
          >
            <div style={{ fontSize: 20, marginBottom: 8 }}>{opt.icon}</div>
            <div style={{ fontSize: 13.5, fontWeight: 600 }}>{opt.label}</div>
          </button>
        ))}
      </div>

      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 14 }}>
        Urgence
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }} id="neo-cfg-urg-grid">
        {URGENCIES.map(u => (
          <button
            key={u.value}
            type="button"
            onClick={() => onChangeUrgency(u.value)}
            className="neo-card"
            style={{
              padding: 16, textAlign: 'left',
              borderColor: urgency === u.value ? 'var(--accent)' : 'var(--border)',
              background: urgency === u.value ? 'var(--bg-subtle)' : 'var(--bg-elevated)',
            }}
          >
            <div style={{ fontSize: 13.5, fontWeight: 600 }}>{u.label}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{u.desc}</div>
          </button>
        ))}
      </div>

      <div style={{ marginTop: 40, display: 'flex', justifyContent: 'space-between' }}>
        <button type="button" className="neo-btn neo-btn-outline" onClick={onBack}>Retour</button>
        <button
          type="button" className="neo-btn neo-btn-primary neo-btn-lg"
          disabled={!intervention} onClick={onNext} style={{ opacity: !intervention ? 0.5 : 1 }}
        >
          Continuer
        </button>
      </div>

      <style>{`
        @media (max-width: 640px) {
          #neo-cfg-interv-grid, #neo-cfg-urg-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}
