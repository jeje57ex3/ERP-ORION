const LOCALES = { fr: 'fr-FR', en: 'en-GB', de: 'de-DE', pt: 'pt-PT' }

export function formatCurrency(n, lang) {
  const locale = LOCALES[lang] || 'fr-FR'
  return Math.round(n).toLocaleString(locale) + ' €'
}
