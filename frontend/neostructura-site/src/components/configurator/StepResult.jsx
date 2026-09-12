import { Link } from 'react-router-dom'

const fmt = (n) => Math.round(n).toLocaleString('fr-FR') + ' €'

function ProjectResult({ references, project }) {
  const { lots, totals } = project
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 44, marginBottom: 16 }}>✓</div>
      <h2 style={{ fontSize: 26, marginBottom: 10 }}>Votre dossier est enregistré</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 24 }}>
        Références <strong style={{ color: 'var(--text)' }}>{references.join(', ')}</strong>
      </p>

      <div style={{ maxWidth: 520, margin: '0 auto' }} className="neo-card">
        <div style={{ padding: 32, textAlign: 'left' }}>
          {lots.map((lot, i) => (
            <div key={i} style={{ padding: '12px 0', borderBottom: i < lots.length - 1 ? '1px solid var(--border)' : 'none' }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{lot.label}</div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                {lot.estimate.requires_diagnostic
                  ? `Diagnostic à partir de ${fmt(lot.estimate.diagnostic_price_from || 0)}`
                  : `${fmt(lot.estimate.price.min)} — ${fmt(lot.estimate.price.max)}`}
              </div>
            </div>
          ))}

          <div style={{ marginTop: 20, paddingTop: 20, borderTop: '2px solid var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Total estimé du dossier</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 600, color: 'var(--accent)' }}>
              {fmt(totals.price_min)} — {fmt(totals.price_max)}
              {totals.any_diagnostic_required && ' (hors diagnostic à confirmer)'}
            </div>
            {totals.visit_necessity && totals.visit_necessity !== 'non_necessaire' && (
              <p style={{ fontSize: 12.5, fontWeight: 600, marginTop: 10 }}>
                {totals.visit_necessity === 'obligatoire'
                  ? 'Une visite sur place sera nécessaire avant validation définitive.'
                  : 'Une visite sur place est recommandée pour confirmer ce chiffrage.'}
              </p>
            )}
          </div>
        </div>
      </div>

      <Link to="/" className="neo-btn neo-btn-outline" style={{ marginTop: 40 }}>
        Retour à l'accueil
      </Link>
    </div>
  )
}

export default function StepResult({ result }) {
  if (result.isProject) return <ProjectResult references={result.references} project={result.project} />

  const { reference, estimate } = result

  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 44, marginBottom: 16 }}>✓</div>
      <h2 style={{ fontSize: 26, marginBottom: 10 }}>Votre demande est enregistrée</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 8 }}>
        Référence <strong style={{ color: 'var(--text)' }}>{reference}</strong>
      </p>

      {estimate ? (
        <div style={{ maxWidth: 480, margin: '32px auto 0' }} className="neo-card">
          <div style={{ padding: 36 }}>
            {estimate.danger_detected && estimate.safety_message && (
              <div style={{ background: '#FDECEA', color: '#C0392B', padding: '12px 16px', borderRadius: 8, fontSize: 13.5, marginBottom: 20, textAlign: 'left' }}>
                ⚠️ {estimate.safety_message}
              </div>
            )}

            <div className="neo-badge" style={{ marginBottom: 16 }}>
              {estimate.requires_diagnostic ? 'Diagnostic sur place nécessaire' : 'Estimation indicative'}
            </div>

            {estimate.requires_diagnostic ? (
              <>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(24px, 3.5vw, 32px)', fontWeight: 600, color: 'var(--accent)' }}>
                  Diagnostic à partir de {fmt(estimate.diagnostic_price_from || 0)}
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 8 }}>
                  Intervention estimée ensuite entre {fmt(estimate.intervention_estimate?.min || 0)} et {fmt(estimate.intervention_estimate?.max || 0)} — confirmée après diagnostic sur place.
                </div>
              </>
            ) : (
              <>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(28px, 4vw, 38px)', fontWeight: 600, color: 'var(--accent)' }}>
                  {fmt(estimate.price.min)} — {fmt(estimate.price.max)}
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6 }}>HT · soit ~{fmt(estimate.price.total_ttc_avg)} TTC</div>
              </>
            )}

            <div style={{ display: 'flex', justifyContent: 'center', gap: 32, marginTop: 28, paddingTop: 24, borderTop: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Durée estimée</div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>
                  {estimate.duration.min}—{estimate.duration.max}h
                </div>
              </div>
            </div>

            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 24, lineHeight: 1.6 }}>
              {estimate.requires_diagnostic
                ? "Cette estimation n'est pas un diagnostic confirmé. Notre équipe vous recontacte pour planifier une visite."
                : 'Le montant définitif sera confirmé après analyse technique. Notre équipe vous recontacte très prochainement.'}
            </p>

            {estimate.visit_necessity && estimate.visit_necessity !== 'non_necessaire' && (
              <p style={{ fontSize: 12.5, fontWeight: 600, marginTop: 10 }}>
                {estimate.visit_necessity === 'obligatoire'
                  ? 'Une visite sur place sera nécessaire avant validation définitive.'
                  : 'Une visite sur place est recommandée pour confirmer ce chiffrage.'}
              </p>
            )}
          </div>
        </div>
      ) : (
        <p style={{ color: 'var(--text-muted)', maxWidth: 420, margin: '24px auto 0' }}>
          Notre équipe va étudier votre demande et revient vers vous rapidement avec une estimation personnalisée.
        </p>
      )}

      <Link to="/" className="neo-btn neo-btn-outline" style={{ marginTop: 40 }}>
        Retour à l'accueil
      </Link>
    </div>
  )
}
