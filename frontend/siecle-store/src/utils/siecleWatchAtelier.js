import { SIECLE_WATCH_MODEL, SIECLE_WATCH_OPTIONS } from '../data/siecleWatchAtelierOptions'

export function calculateAtelierPrice(configuration) {
  let total = SIECLE_WATCH_MODEL.basePrice
  const selectedOptions = []

  Object.values(SIECLE_WATCH_OPTIONS).flat().forEach(group => {
    if (group.type === 'engraving') {
      if (configuration.engraving?.enabled && configuration.engraving?.text) {
        total += group.priceDelta || 0
        selectedOptions.push({ label: 'Gravure', value: configuration.engraving.text, priceDelta: group.priceDelta || 0 })
      }
      return
    }

    const selectedId = configuration[group.key]
    const option = group.options?.find(item => item.id === selectedId)
    if (option) {
      total += option.priceDelta || 0
      selectedOptions.push({ label: group.title, value: option.label, priceDelta: option.priceDelta || 0 })
    }
  })

  return { basePrice: SIECLE_WATCH_MODEL.basePrice, total, selectedOptions }
}

export function calculateHarmonyScore(configuration) {
  let score = 86

  const darkCombo = configuration.caseFinish === 'black_pvd' && configuration.dial === 'black'
  const champagneCombo = configuration.caseFinish === 'champagne_gold' && ['black', 'champagne', 'ivory'].includes(configuration.dial)
  const redCombo = configuration.dial === 'red_velvet' || configuration.strap === 'red_leather' || configuration.caseFinish === 'red_signature'
  const bordeauxCombo = configuration.dial === 'bordeaux' && (configuration.caseFinish === 'rose_gold' || configuration.strap === 'brown_leather')

  if (darkCombo) score += 6
  if (champagneCombo) score += 7
  if (redCombo) score += 4
  if (bordeauxCombo) score += 5
  if (configuration.hands === 'gold' && ['champagne_gold', 'rose_gold'].includes(configuration.caseFinish)) score += 3
  if (configuration.hands === 'champagne' && configuration.caseFinish === 'black_pvd') score += 3
  if (configuration.engraving?.enabled && configuration.engraving?.text) score += 1

  return Math.min(score, 99)
}

export function generateAtelierStory(configuration) {
  const finish = configuration.caseFinish
  const dial = configuration.dial
  const strap = configuration.strap

  if (finish === 'black_pvd' && dial === 'black') {
    return 'Une composition sombre et précise, pensée pour une présence discrète mais impossible à ignorer.'
  }
  if (dial === 'red_velvet' || strap === 'red_leather' || finish === 'red_signature') {
    return 'Une création audacieuse, portée par une tension rouge signature et des détails qui affichent une volonté claire.'
  }
  if (finish === 'champagne_gold' && dial === 'black') {
    return 'La lumière champagne sur le noir : un équilibre entre sobriété et éclat, impossible à reproduire.'
  }
  if (finish === 'champagne_gold') {
    return 'Une montre lumineuse, équilibrée par une finition champagne et une allure intemporelle.'
  }
  if (dial === 'bordeaux' || strap === 'brown_leather') {
    return 'La chaleur bordeaux pose une empreinte élégante — ni discrète, ni ostentatoire. Distincte.'
  }
  if (dial === 'blue_night') {
    return "La profondeur du bleu nuit renvoie à l'essentiel : une montre que l'on remarque sans comprendre pourquoi."
  }
  if (dial === 'green') {
    return 'Un cadran vert émeraude, code couleur de ceux qui savent — précis, affirmé, reconnaissable.'
  }
  if (dial === 'ivory') {
    return "L'ivoire évoque une noblesse discrète. Une montre qui n'a pas besoin de montrer qu'elle est là."
  }
  return 'Une création équilibrée, façonnée pour accompagner votre style avec une précision propre à SIÈCLE.'
}

export const CASE_FINISH_COLORS = {
  polished_steel: { base: '#C8C8C8', highlight: '#E8E8E8', shadow: '#8A8A8A', stroke: '#DCDCDC' },
  champagne_gold:  { base: '#C8A054', highlight: '#E0C070', shadow: '#7A5818', stroke: '#D4B060' },
  rose_gold:       { base: '#C0826A', highlight: '#D89A82', shadow: '#784030', stroke: '#CC9076' },
  black_pvd:       { base: '#1A1A1A', highlight: '#333333', shadow: '#000000', stroke: '#2A2A2A' },
  red_signature:   { base: '#8B1A28', highlight: '#B02035', shadow: '#500010', stroke: '#A02030' },
}

export const DIAL_COLORS = {
  black:     '#060606',
  green:     '#005F30',
  champagne: '#C8A878',
  red_velvet: '#6B1520',
  blue_night: '#0A1830',
  ivory:     '#EEE6D8',
  bordeaux:  '#3D0E18',
}

export const HANDS_COLORS = {
  silver:   '#E0E0E0',
  gold:     '#D4AF70',
  black:    '#1A1A1A',
  red:      '#B01830',
  champagne:'#D0BE96',
}

export const CROWN_COLORS = {
  silver: '#D8D8D8',
  gold:   '#D4AF70',
  black:  '#1A1A1A',
  red:    '#B01830',
}

export const STRAP_COLORS = {
  jubilee_steel:   { fill: '#B8B8B8', accent: '#D0D0D0', type: 'metal' },
  black_leather:   { fill: '#1A1A1A', accent: '#2A2A2A', type: 'leather' },
  brown_leather:   { fill: '#6B4226', accent: '#8A5A34', type: 'leather' },
  red_leather:     { fill: '#8B1A28', accent: '#B02035', type: 'leather' },
  champagne_mesh:  { fill: '#C8A054', accent: '#E0C070', type: 'mesh' },
  black_silicone:  { fill: '#252525', accent: '#303030', type: 'rubber' },
}

export const CASE_SIZE_SCALE = {
  '36mm': 0.90,
  '39mm': 1.00,
  '41mm': 1.07,
}
