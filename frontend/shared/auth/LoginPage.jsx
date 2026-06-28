import React, { useState } from 'react';
import { AuthLayout } from './AuthLayout';
import { useBrand } from '../brand/BrandProvider';

export function LoginPage() {
  const { brandKey, brandConfig } = useBrand();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/v1/auth/customer/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password, brand_key: brandKey, remember_me: rememberMe }),
      });
      const data = await res.json();

      if (!res.ok) {
        setError(data.error || 'Identifiants incorrects.');
        return;
      }

      window.location.href = data.redirect || brandConfig.accountPath;
    } catch {
      setError('Erreur de connexion. Veuillez réessayer.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout>
      <div className="auth-form-card">
        <h2 className="auth-form-card__title">Connexion</h2>
        <p className="auth-form-card__subtitle">
          Bienvenue chez {brandConfig.displayName}
        </p>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="auth-field">
            <label htmlFor="auth-email">Adresse e-mail</label>
            <input
              id="auth-email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="votre@email.fr"
              required
              autoComplete="email"
            />
          </div>

          <div className="auth-field">
            <label htmlFor="auth-password">Mot de passe</label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />
          </div>

          <div className="auth-field" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input
              id="auth-remember"
              type="checkbox"
              checked={rememberMe}
              onChange={e => setRememberMe(e.target.checked)}
              style={{ width: 'auto' }}
            />
            <label htmlFor="auth-remember" style={{ textTransform: 'none', marginBottom: 0, cursor: 'pointer' }}>
              Se souvenir de moi
            </label>
          </div>

          <button
            type="submit"
            className="orion-btn primary auth-submit"
            disabled={loading}
          >
            {loading ? 'Connexion...' : 'Se connecter'}
          </button>
        </form>

        <div className="auth-links-row" style={{ marginTop: '1.5rem' }}>
          <a href={`${brandConfig.homePath}inscription/`} className="auth-link">
            Créer un compte
          </a>
          <a href={`${brandConfig.homePath}mot-de-passe-oublie/`} className="auth-link">
            Mot de passe oublié ?
          </a>
        </div>
      </div>
    </AuthLayout>
  );
}
