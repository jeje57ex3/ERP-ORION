import React from 'react';
import { useBrand } from './BrandProvider';

export function BrandSwitchWarningModal({ targetBrand, onConfirm, onCancel }) {
  const { brandConfig } = useBrand();

  const targetNames = { siecle: 'SIÈCLE', lunea: 'LUNEA' };
  const targetName = targetNames[targetBrand] || targetBrand;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      background: 'rgba(0,0,0,0.7)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius)',
        padding: '2rem',
        maxWidth: 400,
        width: '90%',
        color: 'var(--color-text)',
        fontFamily: 'var(--font-body)',
        boxShadow: 'var(--shadow)',
      }}>
        <h3 style={{ fontFamily: 'var(--font-heading)', color: 'var(--color-primary)', marginBottom: '0.75rem' }}>
          Changer de marque ?
        </h3>
        <p style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', marginBottom: '1.5rem' }}>
          Vous allez quitter <strong>{brandConfig.name}</strong> et accéder à <strong>{targetName}</strong>.
          Votre panier {brandConfig.name} sera conservé séparément.
        </p>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
          <button className="btn-outline" onClick={onCancel}>Annuler</button>
          <button className="orion-btn primary" onClick={onConfirm}>Continuer vers {targetName}</button>
        </div>
      </div>
    </div>
  );
}
