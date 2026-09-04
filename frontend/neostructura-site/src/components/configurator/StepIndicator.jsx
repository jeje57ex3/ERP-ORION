const LABELS = ['Métiers', 'Matériel', 'Intervention', 'Bâtiment', 'Coordonnées']

export default function StepIndicator({ step }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 48 }}>
      {LABELS.map((label, i) => {
        const n = i + 1
        const active = n === step
        const done = n < step
        return (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, flex: i < LABELS.length - 1 ? 1 : 'unset' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 30, height: 30, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 13, fontWeight: 700,
                background: done || active ? 'var(--surface-brand)' : 'var(--bg-subtle)',
                color: done || active ? 'var(--surface-brand-fg)' : 'var(--text-muted)',
                flexShrink: 0,
              }}>
                {done ? '✓' : n}
              </div>
              <span style={{
                fontSize: 13, fontWeight: 600,
                color: active ? 'var(--text)' : 'var(--text-muted)',
                whiteSpace: 'nowrap',
              }} className="neo-step-label">
                {label}
              </span>
            </div>
            {i < LABELS.length - 1 && (
              <div style={{ flex: 1, height: 1, background: done ? 'var(--accent)' : 'var(--border)', minWidth: 24 }} />
            )}
          </div>
        )
      })}
      <style>{`
        @media (max-width: 640px) { .neo-step-label { display: none; } }
      `}</style>
    </div>
  )
}
