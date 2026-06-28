export const SIECLE_WATCH_MODEL = {
  id: 'classic-date',
  name: 'Classic Date',
  atelierName: 'Atelier SIÈCLE',
  basePrice: 319,
  currency: '€',
}

export const SIECLE_WATCH_STEPS = [
  {
    key: 'silhouette',
    label: 'Silhouette',
    title: 'Choisissez la silhouette',
    description: 'La taille et la présence de votre montre.',
  },
  {
    key: 'matter',
    label: 'Matière',
    title: 'Définissez la matière',
    description: 'Acier, champagne, noir ou rouge signature.',
  },
  {
    key: 'dial',
    label: 'Cadran',
    title: 'Donnez le ton du cadran',
    description: "La couleur qui impose l'identité de votre montre.",
  },
  {
    key: 'details',
    label: 'Détails',
    title: 'Signez les détails',
    description: 'Aiguilles, index, lunette et couronne.',
  },
  {
    key: 'strap',
    label: 'Bracelet',
    title: 'Habillez le bracelet',
    description: 'Métal, cuir ou maille premium.',
  },
  {
    key: 'engraving',
    label: 'Gravure',
    title: 'Gravez votre histoire',
    description: 'Initiales, date ou message personnel.',
  },
  {
    key: 'signature',
    label: 'Signature',
    title: 'Votre création finale',
    description: 'Résumé, harmonie et ajout au panier.',
  },
]

export const SIECLE_WATCH_PRESETS = [
  {
    id: 'noir-absolu',
    name: 'Noir Absolu',
    description: 'Une présence sombre, radicale et précise.',
    configuration: {
      caseSize: '39mm',
      caseFinish: 'black_pvd',
      bezel: 'smooth',
      dial: 'black',
      indexes: 'minimal',
      hands: 'champagne',
      strap: 'black_leather',
      crown: 'black',
      glass: 'anti_reflect',
      engraving: { enabled: false, text: '' },
    },
  },
  {
    id: 'rouge-signature',
    name: 'Rouge Signature',
    description: 'Une montre qui impose une identité forte.',
    configuration: {
      caseSize: '39mm',
      caseFinish: 'black_pvd',
      bezel: 'red_signature',
      dial: 'red_velvet',
      indexes: 'baton',
      hands: 'champagne',
      strap: 'red_leather',
      crown: 'red',
      glass: 'clear',
      engraving: { enabled: false, text: '' },
    },
  },
  {
    id: 'champagne-nuit',
    name: 'Champagne Nuit',
    description: "L'élégance noire relevée par une lumière champagne.",
    configuration: {
      caseSize: '39mm',
      caseFinish: 'champagne_gold',
      bezel: 'fluted',
      dial: 'black',
      indexes: 'roman',
      hands: 'gold',
      strap: 'champagne_mesh',
      crown: 'gold',
      glass: 'anti_reflect',
      engraving: { enabled: false, text: '' },
    },
  },
  {
    id: 'bordeaux-elegance',
    name: 'Bordeaux Élégance',
    description: 'Un équilibre entre chaleur, profondeur et distinction.',
    configuration: {
      caseSize: '36mm',
      caseFinish: 'rose_gold',
      bezel: 'smooth',
      dial: 'bordeaux',
      indexes: 'baton',
      hands: 'gold',
      strap: 'brown_leather',
      crown: 'gold',
      glass: 'clear',
      engraving: { enabled: false, text: '' },
    },
  },
]

export const SIECLE_WATCH_OPTIONS = {
  silhouette: [
    {
      key: 'caseSize',
      title: 'Taille du boîtier',
      type: 'choice',
      options: [
        { id: '36mm', label: '36mm', priceDelta: 0 },
        { id: '39mm', label: '39mm', priceDelta: 0 },
        { id: '41mm', label: '41mm', priceDelta: 20 },
      ],
    },
  ],
  matter: [
    {
      key: 'caseFinish',
      title: 'Finition du boîtier',
      type: 'color',
      options: [
        { id: 'polished_steel', label: 'Acier poli', color: '#d8d8d8', priceDelta: 0 },
        { id: 'champagne_gold', label: 'Or champagne', color: '#d7b98c', priceDelta: 70 },
        { id: 'rose_gold', label: 'Or rosé', color: '#c98f72', priceDelta: 80 },
        { id: 'black_pvd', label: 'Noir PVD', color: '#111111', priceDelta: 60 },
        { id: 'red_signature', label: 'Rouge Signature', color: '#b21f35', priceDelta: 75 },
      ],
    },
  ],
  dial: [
    {
      key: 'dial',
      title: 'Couleur du cadran',
      type: 'color',
      options: [
        { id: 'black', label: 'Noir profond', color: '#050505', priceDelta: 0 },
        { id: 'green', label: 'Vert émeraude', color: '#00a85a', priceDelta: 0 },
        { id: 'champagne', label: 'Champagne', color: '#d7b98c', priceDelta: 20 },
        { id: 'red_velvet', label: 'Rouge velours', color: '#8f1d2c', priceDelta: 25 },
        { id: 'blue_night', label: 'Bleu nuit', color: '#0b1c3d', priceDelta: 20 },
        { id: 'ivory', label: 'Ivoire', color: '#f6efe4', priceDelta: 15 },
        { id: 'bordeaux', label: 'Bordeaux', color: '#4d1119', priceDelta: 25 },
      ],
    },
  ],
  details: [
    {
      key: 'bezel',
      title: 'Lunette',
      type: 'choice',
      options: [
        { id: 'fluted', label: 'Cannelée', priceDelta: 0 },
        { id: 'smooth', label: 'Lisse', priceDelta: 0 },
        { id: 'diamond', label: 'Sertie', priceDelta: 90 },
        { id: 'red_signature', label: 'Rouge Signature', priceDelta: 45 },
      ],
    },
    {
      key: 'indexes',
      title: 'Index',
      type: 'choice',
      options: [
        { id: 'baton', label: 'Bâtons', priceDelta: 0 },
        { id: 'roman', label: 'Romains', priceDelta: 20 },
        { id: 'minimal', label: 'Minimal', priceDelta: 0 },
      ],
    },
    {
      key: 'hands',
      title: 'Aiguilles',
      type: 'color',
      options: [
        { id: 'silver', label: 'Argent', color: '#e1e1e1', priceDelta: 0 },
        { id: 'gold', label: 'Or', color: '#d7b98c', priceDelta: 15 },
        { id: 'black', label: 'Noir', color: '#050505', priceDelta: 10 },
        { id: 'red', label: 'Rouge', color: '#b21f35', priceDelta: 15 },
        { id: 'champagne', label: 'Champagne', color: '#d8c7a3', priceDelta: 15 },
      ],
    },
    {
      key: 'crown',
      title: 'Couronne',
      type: 'color',
      options: [
        { id: 'silver', label: 'Argent', color: '#d8d8d8', priceDelta: 0 },
        { id: 'gold', label: 'Or', color: '#d7b98c', priceDelta: 15 },
        { id: 'black', label: 'Noir', color: '#050505', priceDelta: 10 },
        { id: 'red', label: 'Rouge', color: '#b21f35', priceDelta: 15 },
      ],
    },
  ],
  strap: [
    {
      key: 'strap',
      title: 'Bracelet',
      type: 'choice',
      options: [
        { id: 'jubilee_steel', label: 'Acier 5 maillons', priceDelta: 0 },
        { id: 'black_leather', label: 'Cuir noir', priceDelta: 40 },
        { id: 'brown_leather', label: 'Cuir brun', priceDelta: 40 },
        { id: 'red_leather', label: 'Cuir rouge', priceDelta: 50 },
        { id: 'champagne_mesh', label: 'Maille champagne', priceDelta: 70 },
        { id: 'black_silicone', label: 'Silicone noir', priceDelta: 25 },
      ],
    },
  ],
  engraving: [
    {
      key: 'engraving',
      title: 'Gravure',
      type: 'engraving',
      maxLength: 24,
      priceDelta: 25,
    },
  ],
  signature: [],
}
