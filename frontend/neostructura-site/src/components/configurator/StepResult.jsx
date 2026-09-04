import { Link } from 'react-router-dom'

const fmt = (n) => Math.round(n).toLocaleString('fr-FR') + ' €'

export default function StepResult({ result }) {
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
            <div className="neo-badge" style={{ marginBottom: 16 }}>Estimation indicative</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(28px, 4vw, 38px)', fontWeight: 600, color: 'var(--accent)' }}>
              {fmt(estimate.min_ht)} — {fmt(estimate.max_ht)}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6 }}>HT · soit ~{fmt(estimate.total_ttc)} TTC</div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: 32, marginTop: 28, paddingTop: 24, borderTop: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>Durée estimée</div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>
                  {estimate.duration_min_days}—{estimate.duration_max_days} jours
                </div>
              </div>
            </div>

            {estimate.items?.length > 0 && (
              <div style={{ marginTop: 28, paddingTop: 24, borderTop: '1px solid var(--border)', textAlign: 'left' }}>
                <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 12 }}>
                  Détail des postes
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {estimate.items.map((it, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
                      <span style={{ color: 'var(--text)' }}>
                        {it.description}
                        {it.quantity > 1 && <span style={{ color: 'var(--text-muted)' }}> × {it.quantity}</span>}
                      </span>
                      <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{fmt(it.total_avg)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 24, lineHeight: 1.6 }}>
              Le montant définitif sera confirmé après étude technique. Notre équipe vous
              recontacte très prochainement.
            </p>
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
