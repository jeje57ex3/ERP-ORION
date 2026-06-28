export const THEME_CONFIG = {
  // ── SIÈCLE themes ──────────────────────────────────────────────────────────
  'siecle-noir-champagne': {
    brand: 'siecle',
    label: 'Noir Champagne',
    bodyClass: 'theme-siecle-noir-champagne',
    preview: '#C9A96E',
  },
  'siecle-ivoire-or': {
    brand: 'siecle',
    label: 'Ivoire & Or',
    bodyClass: 'theme-siecle-ivoire-or',
    preview: '#D4AF37',
  },
  'siecle-gris-ardoise': {
    brand: 'siecle',
    label: 'Gris Ardoise',
    bodyClass: 'theme-siecle-gris-ardoise',
    preview: '#708090',
  },
  'siecle-rouge-signature': {
    brand: 'siecle',
    label: 'Rouge Signature',
    bodyClass: 'theme-siecle-rouge-signature',
    preview: '#8B0000',
  },

  // ── LUNEA themes ───────────────────────────────────────────────────────────
  'lunea-blanc-nacre': {
    brand: 'lunea',
    label: 'Blanc Nacré',
    bodyClass: 'theme-lunea-blanc-nacre',
    preview: '#F5F0EB',
  },
  'lunea-rose-poudre': {
    brand: 'lunea',
    label: 'Rose Poudré',
    bodyClass: 'theme-lunea-rose-poudre',
    preview: '#E8B4B8',
  },
  'lunea-violet-eclat': {
    brand: 'lunea',
    label: 'Violet Éclat',
    bodyClass: 'theme-lunea-violet-eclat',
    preview: '#7B5EA7',
  },
  'lunea-noir-elegance': {
    brand: 'lunea',
    label: 'Noir Élégance',
    bodyClass: 'theme-lunea-noir-elegance',
    preview: '#1a1a2e',
  },
  'lunea-red-velvet': {
    brand: 'lunea',
    label: 'Red Velvet',
    bodyClass: 'theme-lunea-red-velvet',
    preview: '#8B1A1A',
  },
};

export function getThemeConfig(themeKey) {
  return THEME_CONFIG[themeKey] || THEME_CONFIG['siecle-noir-champagne'];
}

export function getThemesForBrand(brandKey) {
  return Object.entries(THEME_CONFIG)
    .filter(([, cfg]) => cfg.brand === brandKey)
    .map(([key, cfg]) => ({ key, ...cfg }));
}
