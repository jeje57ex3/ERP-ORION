export function parseEuroPrice(value) {
  if (typeof value === 'number') return value
  return Number(
    String(value)
      .replace('€', '')
      .replace(',', '.')
      .replace(/\s/g, '')
  ) || 0
}

export function calculatePointsForProduct(price) {
  return Math.floor(parseEuroPrice(price))
}

export function formatPoints(points) {
  if (!points || points <= 0) return '0 point'
  if (points === 1) return '1 point'
  return `${points} points`
}
