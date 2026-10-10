// Données structurelles uniquement (id, catégorie liée à un métier) — les
// textes affichés (titre, lieu, durée) vivent dans les dictionnaires de
// traduction (src/i18n/dictionaries/*.js, clé `realisationsContent`), et le
// libellé de catégorie réutilise `metiersContent[categorySlug].name` pour
// éviter de traduire deux fois la même chose.
export const REALISATIONS = [
  { id: 1, categorySlug: 'electricite' },
  { id: 2, categorySlug: 'domotique' },
  { id: 3, categorySlug: 'etancheite' },
  { id: 4, categorySlug: 'informatique' },
  { id: 5, categorySlug: 'renovation' },
  { id: 6, categorySlug: 'maintenance' },
]
