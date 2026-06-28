import React from 'react';
import { AuthBrandPanel } from './AuthBrandPanel';
import { AuthExitButton } from './AuthExitButton';
import './auth.css';

export function AuthLayout({ children }) {
  return (
    <div className="auth-layout">
      <AuthExitButton />
      <AuthBrandPanel />
      <div className="auth-form-panel">
        {children}
      </div>
    </div>
  );
}
