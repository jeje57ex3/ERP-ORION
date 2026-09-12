const inputStyle = {
  width: '100%', padding: '11px 13px', borderRadius: 8, border: '1px solid var(--border)',
  background: 'var(--bg)', color: 'var(--text)', fontFamily: 'inherit', fontSize: 14,
}
const labelStyle = { display: 'block', fontSize: 13.5, fontWeight: 600, marginBottom: 8 }

// Valeur sentinelle envoyée quand le client répond "Je ne sais pas" — doit
// correspondre exactement à apps.configurator.services.confidence.DONT_KNOW.
export const DONT_KNOW = '__dont_know__'

function ChoiceRow({ options, value, onChange, multi }) {
  const selected = (opt) => multi ? (Array.isArray(value) && value.includes(opt.value)) : value === opt.value
  const toggle = (opt) => {
    if (!multi) return onChange(opt.value)
    const current = Array.isArray(value) ? value : []
    onChange(current.includes(opt.value) ? current.filter(v => v !== opt.value) : [...current, opt.value])
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {options.map(opt => (
        <button
          key={opt.value} type="button" onClick={() => toggle(opt)}
          className="neo-card"
          style={{
            padding: '9px 15px', fontSize: 13, fontWeight: 600,
            borderColor: selected(opt) ? 'var(--accent)' : 'var(--border)',
            background: selected(opt) ? 'var(--accent)' : 'var(--bg-elevated)',
            color: selected(opt) ? 'var(--accent-contrast)' : 'var(--text)',
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export default function DynamicQuestion({ question, value, onChange }) {
  const { type, label, help_text: helpText, options, allow_dont_know: allowDontKnow } = question
  const isUnknown = value === DONT_KNOW
  // Photo/fichier n'ont pas de sens à "je ne sais pas" — le client peut
  // simplement ne pas en envoyer.
  const canSayDontKnow = allowDontKnow !== false && type !== 'photo' && type !== 'file'

  return (
    <div style={{ marginBottom: 22 }}>
      <label style={labelStyle}>{label}{question.required && <span style={{ color: 'var(--accent)' }}> *</span>}</label>
      {helpText && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, marginTop: -4 }}>{helpText}</div>}

      {isUnknown ? (
        <div style={{ fontSize: 13, color: 'var(--text-muted)', fontStyle: 'italic' }}>
          Je ne sais pas — nous nous en occuperons.{' '}
          <button type="button" onClick={() => onChange('')} className="neo-link" style={{ fontStyle: 'normal' }}>
            Répondre quand même
          </button>
        </div>
      ) : (
        <>
      {(type === 'single_choice') && <ChoiceRow options={options} value={value} onChange={onChange} />}
      {(type === 'multi_choice') && <ChoiceRow options={options} value={value} onChange={onChange} multi />}

      {type === 'boolean' && (
        <div style={{ display: 'flex', gap: 8 }}>
          {[['true', 'Oui'], ['false', 'Non']].map(([v, l]) => (
            <button
              key={v} type="button" onClick={() => onChange(v === 'true')}
              className="neo-card"
              style={{
                padding: '9px 20px', fontSize: 13, fontWeight: 600,
                borderColor: String(value) === v ? 'var(--accent)' : 'var(--border)',
                background: String(value) === v ? 'var(--accent)' : 'var(--bg-elevated)',
                color: String(value) === v ? 'var(--accent-contrast)' : 'var(--text)',
              }}
            >{l}</button>
          ))}
        </div>
      )}

      {(type === 'number' || type === 'surface' || type === 'distance') && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <input
            type="number" min="0" value={value ?? ''}
            onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
          {type === 'surface' && <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>m²</span>}
          {type === 'distance' && <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>km</span>}
        </div>
      )}

      {(type === 'text' || type === 'address') && (
        <input type="text" value={value || ''} onChange={(e) => onChange(e.target.value)} style={inputStyle} />
      )}

      {type === 'zip_code' && (
        <input type="text" maxLength={10} value={value || ''} onChange={(e) => onChange(e.target.value)} style={{ ...inputStyle, width: 140 }} />
      )}

      {type === 'slider' && (
        <div>
          <input type="range" min="0" max="100" value={value ?? 50} onChange={(e) => onChange(Number(e.target.value))} style={{ width: '100%' }} />
          <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'right' }}>{value ?? 50}</div>
        </div>
      )}

      {(type === 'photo' || type === 'file') && (
        <div>
          <input
            type="file" multiple accept={type === 'photo' ? 'image/*' : undefined}
            onChange={(e) => onChange(Array.from(e.target.files || []))}
          />
          {Array.isArray(value) && value.length > 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
              {value.length} fichier(s) sélectionné(s)
            </div>
          )}
        </div>
      )}
        </>
      )}

      {canSayDontKnow && !isUnknown && (
        <button
          type="button" onClick={() => onChange(DONT_KNOW)}
          style={{
            marginTop: 8, background: 'none', border: 'none', padding: 0,
            fontSize: 12, color: 'var(--text-muted)', textDecoration: 'underline', cursor: 'pointer',
          }}
        >
          Je ne sais pas / je préfère être accompagné
        </button>
      )}
    </div>
  )
}
