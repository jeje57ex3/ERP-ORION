// Données structurelles uniquement (slug, icône, ordre) — les textes
// affichés (nom, description, prestations, technologies...) vivent dans
// les dictionnaires de traduction (src/i18n/dictionaries/*.js, clé
// `metiersContent`) pour rester traduisibles en FR/EN/DE/PT.
export const METIERS = [
  { slug: 'electricite', icon: '⚡' },
  { slug: 'domotique', icon: '🏠' },
  { slug: 'etancheite', icon: '💧' },
  { slug: 'informatique', icon: '🖥' },
  { slug: 'renovation', icon: '🏗' },
  { slug: 'maintenance', icon: '🔧' },
]
