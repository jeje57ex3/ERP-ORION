export default function StepService({ domain, services, loading, value, onSelect, onBack }) {
  return (
    <div>
      <h2 style={{ fontSize: 24, marginBottom: 8 }}>{domain?.name}</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 32 }}>
        Précisez votre besoin — nous adaptons les questions suivantes en conséquence.
      </p>

      {loading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Chargement…</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {services.map(s => {
            const selected = value === s.code
            return (
              <button
                key={s.code} type="button" onClick={() => onSelect(s.code)}
                className="neo-card"
                style={{
                  padding: '16px 18px', textAlign: 'left', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
                  borderColor: selected ? 'var(--accent)' : 'var(--border)',
                  background: selected ? 'var(--bg-subtle)' : 'var(--bg-elevated)',
                }}
              >
                <div>
                  <div style={{ fontSize: 14.5, fontWeight: 600 }}>{s.name}</div>
                  {s.short_description && (
                    <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 3 }}>{s.short_description}</div>
                  )}
                </div>
                {s.requires_diagnostic && (
                  <span className="neo-badge" style={{ flexShrink: 0 }}>Diagnostic sur place</span>
                )}
              </button>
            )
          })}
        </div>
      )}

      <div style={{ marginTop: 32 }}>
        <button type="button" className="neo-btn neo-btn-outline" onClick={onBack}>Retour</button>
      </div>
    </div>
  )
}
