import React from 'react';
import { useBrand } from './BrandProvider';

const BADGE_STYLES = {
  siecle: { background: '#C9A96E', color: '#0d0d0d' },
  lunea:  { background: '#E8B4B8', color: '#3D1C24' },
};

export function BrandScopeBadge({ brandKey: propBrandKey, size = 'sm' }) {
  const ctx = useBrand();
  const key = propBrandKey || ctx.brandKey;
  const cfg = ctx.brandConfig;
  const style = BADGE_STYLES[key] || BADGE_STYLES.siecle;
  const fs = size === 'sm' ? '0.7rem' : '0.85rem';
  const px = size === 'sm' ? '0.45rem 0.8rem' : '0.6rem 1.1rem';

  return (
    <span
      style={{
        display: 'inline-block',
        background: style.background,
        color: style.color,
        fontSize: fs,
        fontWeight: 700,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        padding: px,
        borderRadius: 3,
        lineHeight: 1,
        fontFamily: 'Inter, sans-serif',
      }}
    >
      {key === 'siecle' ? 'SIÈCLE' : 'LUNEA'}
    </span>
  );
}
