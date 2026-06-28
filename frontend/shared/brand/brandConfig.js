export const BRAND_CONFIG = {
  siecle: {
    key: 'siecle',
    name: 'SIÈCLE',
    displayName: 'SIÈCLE Horlogerie',
    tagline: "L'excellence horlogère française",
    defaultTheme: 'siecle-noir-champagne',
    defaultLanguage: 'fr',
    supportedLanguages: ['fr', 'en', 'es'],
    supportedThemes: [
      'siecle-noir-champagne',
      'siecle-ivoire-or',
      'siecle-gris-ardoise',
      'siecle-rouge-signature',
    ],
    apiBase: '/api/v1/siecle',
    cartStorageKey: 'cart:siecle',
    wishlistStorageKey: 'wishlist:siecle',
    loginPath: '/siecle/login/',
    accountPath: '/siecle/compte/',
    homePath: '/siecle/',
    logoUrl: '/static/siecle/img/logo-siecle.svg',
    favicon: '/static/siecle/img/favicon.svg',
    primaryColor: '#C9A96E',
    accentColor: '#1a1a1a',
  },

  lunea: {
    key: 'lunea',
    name: 'LUNEA',
    displayName: 'LUNEA Beauty',
    tagline: 'Beauté, rituel, lumière',
    defaultTheme: 'lunea-blanc-nacre',
    defaultLanguage: 'fr',
    supportedLanguages: ['fr', 'en', 'es'],
    supportedThemes: [
      'lunea-blanc-nacre',
      'lunea-rose-poudre',
      'lunea-violet-eclat',
      'lunea-noir-elegance',
      'lunea-red-velvet',
    ],
    apiBase: '/api/v1/lunea/store',
    cartStorageKey: 'cart:lunea',
    wishlistStorageKey: 'wishlist:lunea',
    loginPath: '/lunea/login/',
    accountPath: '/lunea/compte/',
    homePath: '/lunea/',
    logoUrl: '/static/lunea/img/logo-lunea.svg',
    favicon: '/static/lunea/img/favicon.svg',
    primaryColor: '#E8B4B8',
    accentColor: '#2d1b2e',
  },
};

export function getBrandConfig(brandKey) {
  return BRAND_CONFIG[brandKey] || BRAND_CONFIG.siecle;
}

export const SUPPORTED_BRANDS = Object.keys(BRAND_CONFIG);
