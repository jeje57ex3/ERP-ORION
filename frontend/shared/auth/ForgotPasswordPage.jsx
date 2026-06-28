import React, { useState } from 'react';
import { AuthLayout } from './AuthLayout';
import { useBrand } from '../brand/BrandProvider';

export function ForgotPasswordPage() {
  const { brandKey, brandConfig } = useBrand();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/v1/auth/customer/password-reset/request/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, brand_key: brandKey }),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error || 'Une erreur est survenue.');
        return;
      }

      setSent(true);
    } catch {
      setError('Erreur réseau. Veuillez réessayer.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <div className="auth-form-card">
        <h2 className="auth-form-card__title">Mot de passe oublié</h2>
        <p className="auth-form-card__subtitle">
          Entrez votre adresse e-mail pour recevoir un lien de réinitialisation.
        </p>

        {error && <div className="auth-error">{error}</div>}

        {sent ? (
          <div className="auth-success">
            Un lien de réinitialisation vous a été envoyé si un compte existe avec cette adresse.
          </div>
        ) : (
          <form onSubmit={handleSubmit} noValidate>
            <div className="auth-field">
              <label htmlFor="reset-email">Adresse e-mail</label>
              <input
                id="reset-email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="votre@email.fr"
                required
                autoComplete="email"
              />
            </div>

            <button
              type="submit"
              className="orion-btn primary auth-submit"
              disabled={loading}
            >
              {loading ? 'Envoi...' : 'Envoyer le lien'}
            </button>
          </form>
        )}

        <div className="auth-links-row" style={{ marginTop: '1.5rem' }}>
          <a href={brandConfig.loginPath} className="auth-link">
            Retour à la connexion
          </a>
        </div>
      </div>
    </AuthLayout>
  );
}
