import React from 'react';
import { useBrand } from '../brand/BrandProvider';

export function AuthExitButton() {
  const { brandConfig } = useBrand();

  function handleExit() {
    window.location.href = brandConfig.homePath;
  }

  return (
    <button className="auth-exit-btn" onClick={handleExit} aria-label="Quitter">
      Quitter
    </button>
  );
}
