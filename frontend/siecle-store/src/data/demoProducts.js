export const DEMO_PRODUCTS = {
  vetements: [
    { id: 'v1', name: 'T-shirt Urban Noir', price: 49, category: 'vetements', sizes: ['XS','S','M','L','XL','2XL','3XL','4XL'], points: 245 },
    { id: 'v2', name: 'Veste Structurée', price: 129, category: 'vetements', sizes: ['S','M','L','XL','2XL'], points: 645 },
    { id: 'v3', name: 'Jean Slim Premium', price: 89, category: 'vetements', sizes: ['XS','S','M','L','XL','2XL','3XL'], points: 445 },
    { id: 'v4', name: 'Hoodie Signature', price: 79, category: 'vetements', sizes: ['S','M','L','XL','2XL','3XL','4XL'], points: 395 },
    { id: 'v5', name: 'Chemise Satin', price: 95, category: 'vetements', sizes: ['S','M','L','XL','2XL'], points: 475 },
    { id: 'v6', name: 'Blazer Oversize', price: 149, category: 'vetements', sizes: ['S','M','L','XL','2XL','3XL'], points: 745 },
  ],
  montres: [
    { id: 'm1', name: 'Urban Noir', price: 289, category: 'montres', material: 'Acier', dial_color: 'Noir mat', strap: 'Cuir brun', movement: 'Quartz japonais', diameter: '40mm', customizable: true, points: 1445 },
    { id: 'm2', name: 'Blanc Minéral', price: 259, category: 'montres', material: 'Titane', dial_color: 'Blanc', strap: 'Milanais', movement: 'Quartz japonais', diameter: '38mm', customizable: true, points: 1295 },
    { id: 'm3', name: 'Brun Élégance', price: 349, category: 'montres', material: 'Bronze', dial_color: 'Sable', strap: 'Cuir brun', movement: 'Automatique', diameter: '42mm', customizable: true, points: 1745 },
    { id: 'm4', name: 'Rose Signature', price: 319, category: 'montres', material: 'Or Rose', dial_color: 'Nude', strap: 'Cuir rose', movement: 'Quartz japonais', diameter: '36mm', customizable: false, points: 1595 },
  ],
  maquillage: [
    { id: 'k1', name: 'FDT Porcelaine 01N', price: 38, category: 'maquillage', points: 190 },
    { id: 'k2', name: 'Rouge Bordeaux Intense', price: 26, category: 'maquillage', points: 130 },
    { id: 'k3', name: 'Mascara Volume Noir', price: 22, category: 'maquillage', points: 110 },
    { id: 'k4', name: 'Palette Smoky 6 Teintes', price: 58, category: 'maquillage', points: 290 },
    { id: 'k5', name: 'Highlighter Doré', price: 34, category: 'maquillage', points: 170 },
    { id: 'k6', name: 'Gloss Nude Transparent', price: 19, category: 'maquillage', points: 95 },
  ],
}

export const getAllProducts = () => Object.values(DEMO_PRODUCTS).flat()
export const getByCategory = (cat) => DEMO_PRODUCTS[cat] || []
