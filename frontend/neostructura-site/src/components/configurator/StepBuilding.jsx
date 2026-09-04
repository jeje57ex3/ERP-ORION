const PROPERTY_TYPES = [
  { value: 'house', label: 'Maison' },
  { value: 'apartment', label: 'Appartement' },
  { value: 'commercial', label: 'Local commercial' },
  { value: 'office', label: 'Bureau' },
  { value: 'workshop', label: 'Atelier' },
  { value: 'building', label: 'Immeuble' },
]

const labelStyle = { display: 'block', fontSize: 12.5, fontWeight: 600, marginBottom: 8, color: 'var(--text-muted)' }
const inputStyle = {
  width: '100%', padding: '12px 14px', borderRadius: 8, border: '1px solid var(--border)',
  background: 'var(--bg)', color: 'var(--text)', fontFamily: 'inherit', fontSize: 14,
}

export default function StepBuilding({ building, onChange, onNext, onBack }) {
  const set = (field) => (e) => onChange({ ...building, [field]: e.target.value })

  return (
    <div>
      <h2 style={{ fontSize: 24, marginBottom: 8 }}>Parlez-nous du bâtiment.</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 32 }}>
        Ces informations nous aident à affiner l'estimation.
      </p>

      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>Type de bâtiment</label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }} id="neo-cfg-prop-grid">
          {PROPERTY_TYPES.map(pt => (
            <button
              key={pt.value} type="button" onClick={() => onChange({ ...building, property_type: pt.value })}
              className="neo-card" style={{
                padding: '12px 14px', fontSize: 13, fontWeight: 600, textAlign: 'left',
                borderColor: building.property_type === pt.value ? 'var(--accent)' : 'var(--border)',
                background: building.property_type === pt.value ? 'var(--bg-subtle)' : 'var(--bg-elevated)',
              }}
            >
              {pt.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }} id="neo-cfg-row1">
        <div>
          <label style={labelStyle}>Surface approximative (m²)</label>
          <input type="number" min="0" value={building.surface || ''} onChange={set('surface')} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Adresse</label>
          <input type="text" value={building.address || ''} onChange={set('address')} style={inputStyle} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }} id="neo-cfg-row2">
        <div>
          <label style={labelStyle}>Code postal</label>
          <input type="text" value={building.zip_code || ''} onChange={set('zip_code')} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Ville</label>
          <input type="text" value={building.city || ''} onChange={set('city')} style={inputStyle} />
        </div>
      </div>

      <div style={{ marginTop: 40, display: 'flex', justifyContent: 'space-between' }}>
        <button type="button" className="neo-btn neo-btn-outline" onClick={onBack}>Retour</button>
        <button type="button" className="neo-btn neo-btn-primary neo-btn-lg" onClick={onNext}>Continuer</button>
      </div>

      <style>{`
        @media (max-width: 640px) {
          #neo-cfg-prop-grid { grid-template-columns: repeat(2, 1fr) !important; }
          #neo-cfg-row1, #neo-cfg-row2 { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}
