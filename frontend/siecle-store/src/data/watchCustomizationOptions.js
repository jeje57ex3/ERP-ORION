export const watchCustomizationOptions = {
  case: [
    { id: 'case_black_steel', label: 'Acier noir',       color: '#0B0B0B', material: 'metal',  priceDelta: 0  },
    { id: 'case_silver',      label: 'Argent poli',      color: '#C0C0C0', material: 'metal',  priceDelta: 20 },
    { id: 'case_gold',        label: 'Doré champagne',   color: '#C9A45C', material: 'metal',  priceDelta: 35 },
    { id: 'case_beige',       label: 'Beige sable',      color: '#D8C7A3', material: 'metal',  priceDelta: 25 },
  ],
  dial: [
    { id: 'dial_black',      label: 'Noir profond',    color: '#000000', material: 'matte',  priceDelta: 0  },
    { id: 'dial_white',      label: 'Blanc cassé',     color: '#F5F1E8', material: 'matte',  priceDelta: 10 },
    { id: 'dial_grey',       label: 'Gris anthracite', color: '#222222', material: 'matte',  priceDelta: 10 },
    { id: 'dial_champagne',  label: 'Champagne',       color: '#D8C7A3', material: 'satin',  priceDelta: 20 },
  ],
  hands: [
    { id: 'hands_silver', label: 'Argent', color: '#C0C0C0', material: 'metal', priceDelta: 0  },
    { id: 'hands_gold',   label: 'Doré',   color: '#C9A45C', material: 'metal', priceDelta: 10 },
    { id: 'hands_black',  label: 'Noir',   color: '#0B0B0B', material: 'metal', priceDelta: 5  },
    { id: 'hands_white',  label: 'Blanc',  color: '#FFFFFF', material: 'gloss', priceDelta: 5  },
  ],
  strap: [
    { id: 'strap_black_leather', label: 'Cuir noir',     color: '#050505', material: 'leather', priceDelta: 0  },
    { id: 'strap_brown_leather', label: 'Cuir brun',     color: '#3A2417', material: 'leather', priceDelta: 15 },
    { id: 'strap_beige',         label: 'Beige premium', color: '#D8C7A3', material: 'leather', priceDelta: 20 },
    { id: 'strap_steel',         label: 'Maille acier',  color: '#A8A8A8', material: 'metal',   priceDelta: 35 },
  ],
}

export const defaultWatchCustomization = {
  case:  'case_black_steel',
  dial:  'dial_black',
  hands: 'hands_silver',
  strap: 'strap_black_leather',
}

export const watchGroupLabels = {
  case:  'Boîtier',
  dial:  'Cadran',
  hands: 'Aiguilles',
  strap: 'Bracelet',
}

export const watchGroupOrder = ['case', 'dial', 'hands', 'strap']

export function getOption(group, id) {
  return watchCustomizationOptions[group]?.find(o => o.id === id)
}

export function calcPriceDelta(customization) {
  return watchGroupOrder.reduce((sum, group) => {
    const opt = getOption(group, customization[group])
    return sum + (opt?.priceDelta ?? 0)
  }, 0)
}
