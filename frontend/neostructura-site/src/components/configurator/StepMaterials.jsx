import { useState } from 'react'
import { METIERS } from '../../data/metiers'

const fmt = (n) => Math.round(n).toLocaleString('fr-FR') + ' €'
const GAMME_LABELS = { standard: 'Standard', premium: 'Premium', luxe: 'Luxe' }

function QtyControl({ option, qty, onSet }) {
  if (option.unit === 'forfait') {
    const checked = qty > 0
    return (
      <button
        type="button"
        onClick={() => onSet(checked ? 0 : 1)}
        className="neo-card"
        style={{
          padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8,
          borderColor: checked ? 'var(--accent)' : 'var(--border)',
          background: checked ? 'var(--bg-subtle)' : 'var(--bg-elevated)',
        }}
      >
        <span style={{
          width: 18, height: 18, borderRadius: 4, border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11,
          background: checked ? 'var(--accent)' : 'transparent', color: 'var(--accent-contrast)',
        }}>
          {checked ? '✓' : ''}
        </span>
        <span style={{ fontSize: 13 }}>{checked ? 'Ajouté' : 'Ajouter'}</span>
      </button>
    )
  }

  if (option.unit === 'm2') {
    return (
      <input
        type="number" min="0" step="1" placeholder="m²"
        value={qty || ''} onChange={(e) => onSet(e.target.value === '' ? 0 : Number(e.target.value))}
        style={{
          width: 84, padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)',
          background: 'var(--bg)', color: 'var(--text)', fontFamily: 'inherit', fontSize: 13.5,
        }}
      />
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <button
        type="button" onClick={() => onSet(Math.max(0, (qty || 0) - 1))}
        disabled={!qty}
        className="neo-card" style={{ width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: qty ? 1 : 0.4 }}
      >−</button>
      <span style={{ minWidth: 20, textAlign: 'center', fontSize: 14, fontWeight: 600 }}>{qty || 0}</span>
      <button
        type="button" onClick={() => onSet((qty || 0) + 1)}
        className="neo-card" style={{ width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >+</button>
    </div>
  )
}

function FamilyRow({ family, materials, onChange, defaultGamme }) {
  const hasMultipleGammes = family.options.length > 1
  const initialOption = family.options.find(o => o.quality_level === defaultGamme) || family.options[0]
  const [activeCode, setActiveCode] = useState(initialOption.code)
  const active = family.options.find(o => o.code === activeCode) || initialOption
  const qty = materials[active.code] || 0

  const selectGamme = (code) => {
    if (code === activeCode) return
    const carriedQty = materials[activeCode] || 0
    const updated = { ...materials, [activeCode]: 0, [code]: carriedQty }
    onChange(updated)
    setActiveCode(code)
  }

  const setQty = (newQty) => onChange({ ...materials, [active.code]: newQty })

  return (
    <div className="neo-card" style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 600 }}>{family.family}</div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {active.brand && <span>{active.brand}{active.reference ? ` — ${active.reference}` : ''} · </span>}
            {fmt(active.price_avg)} / {active.unit_label.toLowerCase()}
          </div>
        </div>
        <QtyControl option={active} qty={qty} onSet={setQty} />
      </div>

      {hasMultipleGammes && (
        <div style={{ display: 'flex', gap: 8 }}>
          {family.options.map(opt => (
            <button
              key={opt.code} type="button" onClick={() => selectGamme(opt.code)}
              style={{
                padding: '5px 12px', borderRadius: 999, fontSize: 11.5, fontWeight: 600,
                border: `1px solid ${opt.code === activeCode ? 'var(--accent)' : 'var(--border)'}`,
                background: opt.code === activeCode ? 'var(--accent)' : 'transparent',
                color: opt.code === activeCode ? 'var(--accent-contrast)' : 'var(--text-muted)',
              }}
            >
              {GAMME_LABELS[opt.quality_level] || opt.quality_level}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function StepMaterials({ metiers, materials, onChange, qualityLevel, onChangeQuality, options, loading, onNext, onBack }) {
  const catalog = options?.materials || {}
  const qualityLevels = options?.quality_levels || []

  return (
    <div>
      <h2 style={{ fontSize: 24, marginBottom: 8 }}>Choisissez votre matériel.</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 32 }}>
        Précisez les équipements et la gamme souhaités — optionnel, notre équipe
        peut aussi évaluer ce point lors du diagnostic.
      </p>

      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 14 }}>
        Gamme par défaut
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 32 }} id="neo-cfg-gamme-grid">
        {qualityLevels.map(q => (
          <button
            key={q.value} type="button" onClick={() => onChangeQuality(q.value)}
            className="neo-card" style={{
              padding: '12px 14px', textAlign: 'center', fontSize: 13, fontWeight: 600,
              borderColor: qualityLevel === q.value ? 'var(--accent)' : 'var(--border)',
              background: qualityLevel === q.value ? 'var(--bg-subtle)' : 'var(--bg-elevated)',
            }}
          >
            {q.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Chargement du catalogue…</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 28, marginBottom: 36 }}>
          {metiers.map(slug => {
            const metier = METIERS.find(m => m.slug === slug)
            const families = catalog[slug] || []
            if (!families.length) return null
            return (
              <div key={slug}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <span style={{ fontSize: 18 }}>{metier?.icon}</span>
                  <span style={{ fontSize: 14, fontWeight: 600 }}>{metier?.name || slug}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {families.map(family => (
                    <FamilyRow
                      key={family.family} family={family} materials={materials}
                      onChange={onChange} defaultGamme={qualityLevel}
                    />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'space-between' }}>
        <button type="button" className="neo-btn neo-btn-outline" onClick={onBack}>Retour</button>
        <button type="button" className="neo-btn neo-btn-primary neo-btn-lg" onClick={onNext}>Continuer</button>
      </div>

      <style>{`
        @media (max-width: 640px) { #neo-cfg-gamme-grid { grid-template-columns: 1fr !important; } }
      `}</style>
    </div>
  )
}
