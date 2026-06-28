import React from 'react';
import { useBrand } from '../brand/BrandProvider';
import { AuthAnimatedBackground } from './AuthAnimatedBackground';

export function AuthBrandPanel() {
  const { brandConfig } = useBrand();

  return (
    <div className="auth-brand-panel">
      <AuthAnimatedBackground />
      <img
        className="auth-brand-panel__logo"
        src={brandConfig.logoUrl}
        alt={brandConfig.name}
        onError={e => { e.target.style.display = 'none'; }}
      />
      <h1 className="auth-brand-panel__name">{brandConfig.name}</h1>
      <p className="auth-brand-panel__tagline">{brandConfig.tagline}</p>
    </div>
  );
}
