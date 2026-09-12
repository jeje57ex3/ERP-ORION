import DynamicQuestion from './DynamicQuestion'
import { useLanguage } from '../../i18n/LanguageContext'
import { formatCurrency } from '../../i18n/format'

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
  const { dict, lang } = useLanguage()
  const t = dict.configurator.questions
  const fmt = (n) => formatCurrency(n, lang)
  const allRequiredAnswered = questions.every(q => isAnswered(q, answers))

  return (
    <div>
      <h2 style={{ fontSize: 24, marginBottom: 8 }}>{service?.name}</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 28 }}>
        {t.title}
      </p>

      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 14 }}>
        {t.urgencyLabel}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 32 }} id="neo-cfg-urg-grid">
        {t.urgencyOptions.map(u => (
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
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>{dict.common.loading}</p>
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
          <div className="neo-badge" style={{ marginBottom: 10 }}>{t.estimatePreviewBadge}</div>
          {liveEstimate.requires_diagnostic ? (
            <>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 600, color: 'var(--accent)' }}>
                {t.diagnosticFrom(fmt(liveEstimate.diagnostic_price_from || 0))}
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 6 }}>
                {t.interventionEstimate(fmt(liveEstimate.intervention_estimate?.min || 0), fmt(liveEstimate.intervention_estimate?.max || 0))}
              </div>
            </>
          ) : (
            <>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: 24, fontWeight: 600, color: 'var(--accent)' }}>
                {fmt(liveEstimate.price.min)} — {fmt(liveEstimate.price.max)}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                HT · {liveEstimate.duration.min}—{liveEstimate.duration.max}{t.durationSuffix}
              </div>
            </>
          )}
        </div>
      )}
      {estimateLoading && <p style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>{t.calculating}</p>}

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <button type="button" className="neo-btn neo-btn-outline" onClick={onBack}>{dict.common.back}</button>
        <div style={{ display: 'flex', gap: 12 }}>
          {onAddAnother && (
            <button
              type="button" className="neo-btn neo-btn-outline"
              disabled={!allRequiredAnswered} onClick={onAddAnother}
              style={{ opacity: allRequiredAnswered ? 1 : 0.5 }}
            >
              {t.addAnother}
            </button>
          )}
          <button
            type="button" className="neo-btn neo-btn-primary neo-btn-lg"
            disabled={!allRequiredAnswered} onClick={onNext}
            style={{ opacity: allRequiredAnswered ? 1 : 0.5 }}
          >
            {dict.common.continue}
          </button>
        </div>
      </div>

      <style>{`
        @media (max-width: 640px) { #neo-cfg-urg-grid { grid-template-columns: 1fr !important; } }
      `}</style>
    </div>
  )
}
