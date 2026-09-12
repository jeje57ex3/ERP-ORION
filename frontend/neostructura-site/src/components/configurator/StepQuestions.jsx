import DynamicQuestion from './DynamicQuestion'

const URGENCIES = [
  { value: 'urgent', label: 'Urgent', desc: 'Sous 48h' },
  { value: 'normal', label: 'Normal', desc: 'Sous 2 semaines' },
  { value: 'flexible', label: 'Flexible', desc: 'Pas de contrainte' },
]

const fmt = (n) => Math.round(n).toLocaleString('fr-FR') + ' €'

function isAnswered(q, answers) {
  const v = answers[q.identifier]
  if (!q.required) return true
  if (Array.isArray(v)) return v.length > 0
  return v !== undefined && v !== '' && v !== null
}

export default function StepQuestions({
  service, questions, loadingQuestions, answers, onAnswerChange,
  urgency, onUrgencyChange, liveEstimate, estimateLoading, onNext, onBack, onAddAnother,
}) {
  const allRequiredAnswered = questions.every(q => isAnswered(q, answers))

  return (
    <div>
      <h2 style={{ fontSize: 24, marginBottom: 8 }}>{service?.name}</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 28 }}>
        Quelques précisions pour affiner votre estimation.
      </p>

      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 14 }}>
        Urgence
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 32 }} id="neo-cfg-urg-grid">
        {URGENCIES.map(u => (
          <button
            key={u.value} type="button" onClick={() => onUrgencyChange(u.value)}
            className="neo-card"
            style={{
              padding: 14, textAlign: 'left',
              borderColor: urgency === u.value ? 'var(--accent)' : 'var(--border)',
              background: urgency === u.value ? 'var(--bg-subtle)' : 'var(--bg-elevated)',
            }}
          >
            <div style={{ fontSize: 13.5, fontWeight: 600 }}>{u.label}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{u.desc}</div>
          </button>
        ))}
      </div>

      {loadingQuestions ? (
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Chargement des questions…</p>
      ) : (
        <div>
          {questions.map(q => (
            <DynamicQuestion
              key={q.identifier} question={q} value={answers[q.identifier]}
              onChange={(val) => onAnswerChange(q.identifier, val)}
            />
          ))}
        </div>
      )}

      {liveEstimate && (
        <div className="neo-card" style={{ padding: 20, marginTop: 8, marginBottom: 8 }}>
          {liveEstimate.danger_detected && liveEstimate.safety_message && (
            <div style={{ background: '#FDECEA', color: '#C0392B', padding: '10px 14px', borderRadius: 8, fontSize: 13, marginBottom: 14 }}>
              ⚠️ {liveEstimate.safety_message}
            </div>
          )}
          <div className="neo-badge" style={{ marginBottom: 10 }}>Estimation indicative</div>
          {liveEstimate.requires_diagnostic ? (
            <>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 600, color: 'var(--accent)' }}>
                Diagnostic à partir de {fmt(liveEstimate.diagnostic_price_from || 0)}
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 6 }}>
                Intervention estimée ensuite entre {fmt(liveEstimate.intervention_estimate?.min || 0)} et {fmt(liveEstimate.intervention_estimate?.max || 0)}, à confirmer sur place.
              </div>
            </>
          ) : (
            <>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 24, fontWeight: 600, color: 'var(--accent)' }}>
                {fmt(liveEstimate.price.min)} — {fmt(liveEstimate.price.max)}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                HT · durée estimée {liveEstimate.duration.min}—{liveEstimate.duration.max}h
              </div>
            </>
          )}
        </div>
      )}
      {estimateLoading && <p style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>Calcul de l'estimation…</p>}

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <button type="button" className="neo-btn neo-btn-outline" onClick={onBack}>Retour</button>
        <div style={{ display: 'flex', gap: 12 }}>
          {onAddAnother && (
            <button
              type="button" className="neo-btn neo-btn-outline"
              disabled={!allRequiredAnswered} onClick={onAddAnother}
              style={{ opacity: allRequiredAnswered ? 1 : 0.5 }}
              title="Ajoute ce besoin au dossier et permet d'en décrire un autre (§12-13)"
            >
              + Ajouter un autre besoin
            </button>
          )}
          <button
            type="button" className="neo-btn neo-btn-primary neo-btn-lg"
            disabled={!allRequiredAnswered} onClick={onNext}
            style={{ opacity: allRequiredAnswered ? 1 : 0.5 }}
          >
            Continuer
          </button>
        </div>
      </div>

      <style>{`
        @media (max-width: 640px) { #neo-cfg-urg-grid { grid-template-columns: 1fr !important; } }
      `}</style>
    </div>
  )
}
