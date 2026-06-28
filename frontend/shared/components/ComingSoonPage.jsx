import { useState } from 'react'
import './coming-soon.css'

export default function ComingSoonPage({
  brand = 'siecle',
  title = 'Bientôt disponible',
  subtitle = 'Cette section arrive prochainement.',
  description = 'Inscrivez-vous pour être informé du lancement.',
  backUrl = '/',
  featureKey = 'general',
}) {
  const [email, setEmail] = useState('')
  const [status, setStatus] = useState('idle')

  const brandLabel = brand === 'lunea' ? 'LUNEA' : 'SIÈCLE'

  async function handleSubmit(event) {
    event.preventDefault()
    if (!email) return
    setStatus('loading')
    try {
      const response = await fetch('/api/v1/waitlist/subscribe/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Brand-Key': brand,
        },
        body: JSON.stringify({ email, brand_key: brand, feature_key: featureKey }),
      })
      if (!response.ok) throw new Error('Erreur inscription')
      setStatus('success')
      setEmail('')
    } catch {
      setStatus('error')
    }
  }

  return (
    <main className={`coming-soon coming-soon-${brand}`}>
      <section className="coming-soon-panel">
        <p className="coming-soon-eyebrow">{brandLabel}</p>

        <h1>{title}</h1>

        <p className="coming-soon-subtitle">{subtitle}</p>

        <p className="coming-soon-description">{description}</p>

        <form onSubmit={handleSubmit} className="coming-soon-form">
          <input
            type="email"
            placeholder="Votre adresse email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <button type="submit" disabled={status === 'loading'}>
            {status === 'loading' ? 'Inscription...' : 'Me prévenir'}
          </button>
        </form>

        {status === 'success' && (
          <p className="coming-soon-success">Merci, vous serez informé du lancement.</p>
        )}
        {status === 'error' && (
          <p className="coming-soon-error">Une erreur est survenue. Réessayez dans quelques instants.</p>
        )}

        <a href={backUrl} className="coming-soon-back">← Retour à l'accueil</a>
      </section>
    </main>
  )
}
