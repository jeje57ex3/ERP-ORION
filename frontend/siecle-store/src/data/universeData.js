export const UNIVERSES = [
  {
    id: 'vetements',
    name: 'Vêtements',
    slug: 'vetements',
    tagline: 'Style inclusif. Du XS au 4XL.',
    color: '#1a1a1a',
    accent: '#D8C7A3',
    href: '/vetements',
    icon: '👕',
    features: ['Grandes tailles', 'Coupes ajustées & oversize', 'Matières premium', 'Guide taille IA'],
  },
  {
    id: 'montres',
    name: 'Montres',
    slug: 'montres',
    tagline: 'Chaque pièce, une signature.',
    color: '#0d0d0d',
    accent: '#C0A875',
    href: '/montres',
    icon: '⌚',
    features: ['Configurateur 3D', 'Gravure personnalisée', 'Certificat d\'authenticité', 'Galerie 3D'],
  },
  {
    id: 'maquillage',
    name: 'Maquillage',
    slug: 'maquillage',
    tagline: 'Beauté pour toutes les carnations.',
    color: '#2D1B1B',
    accent: '#C4956A',
    href: '/maquillage',
    external: true,
    icon: '💄',
    features: ['Quiz beauté personnalisé', 'Trouver ma teinte', 'Toutes carnations', 'Routine sur-mesure'],
  },
]

export const getUniverse = (slug) => UNIVERSES.find(u => u.slug === slug)
