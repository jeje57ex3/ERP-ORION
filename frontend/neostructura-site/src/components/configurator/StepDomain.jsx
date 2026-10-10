import { useLanguage } from '../../i18n/LanguageContext'

export default function StepDomain({ domains, loading, value, onSelect }) {
  const { dict } = useLanguage()
  const t = dict.configurator.domain

  return (
    <div>
      <h2 style={{ fontSize: 24, marginBottom: 8 }}>{t.question}</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 32 }}>
        {t.help}
      </p>

      {loading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>{dict.common.loading}</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }} id="neo-cfg-domain-grid">
          {domains.map(d => {
            const selected = value === d.code
            return (
              <button
                key={d.code} type="button" onClick={() => onSelect(d.code)}
                className="neo-card"
                style={{
                  padding: 24, textAlign: 'left',
                  borderColor: selected ? 'var(--accent)' : 'var(--border)',
                  background: selected ? 'var(--bg-subtle)' : 'var(--bg-elevated)',
                }}
              >
                <div style={{ fontSize: 26, marginBottom: 10 }}>{d.icon}</div>
                <div style={{ fontSize: 14.5, fontWeight: 600, marginBottom: 4 }}>{d.name}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{d.description}</div>
              </button>
            )
          })}
        </div>
      )}

      <style>{`
        @media (max-width: 640px) { #neo-cfg-domain-grid { grid-template-columns: 1fr !important; } }
      `}</style>
    </div>
  )
}
