export const makeupPlaceholders = {
  hero: '/static/placeholders/makeup-hero.jpg',
  foundation: '/static/placeholders/foundation.jpg',
  lipstick: '/static/placeholders/lipstick.jpg',
  palette: '/static/placeholders/palette.jpg',
  highlighter: '/static/placeholders/highlighter.jpg',
  categoryFace: '/static/placeholders/category-face.jpg',
  categoryLips: '/static/placeholders/category-lips.jpg',
  categoryEyes: '/static/placeholders/category-eyes.jpg',
  categoryTools: '/static/placeholders/category-tools.jpg',
}

export const watchPlaceholders = {
  mainWatch: '/static/placeholders/watch-main.png',
  watchDark: '/static/placeholders/watch-dark.jpg',
  watchDetail: '/static/placeholders/watch-detail.jpg',
}

// Gradient placeholder generator for missing images
export function gradientPlaceholder(colors = ['#1a1a1a', '#2a2a2a']) {
  return `linear-gradient(135deg, ${colors.join(', ')})`
}
