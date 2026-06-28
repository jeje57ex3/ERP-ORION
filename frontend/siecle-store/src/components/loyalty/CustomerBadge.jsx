export default function CustomerBadge({ tier = 'BRONZE', size = 'md' }) {
  const COLORS = { BRONZE: '#CD7F32', SILVER: '#C0C0C0', GOLD: '#D8C7A3', PLATINUM: '#fff' }
  const ICONS = { BRONZE: '🥉', SILVER: '🥈', GOLD: '🥇', PLATINUM: '💎' }
  const SIZES = { sm: { font: 10, pad: '3px 10px' }, md: { font: 12, pad: '6px 16px' }, lg: { font: 14, pad: '10px 22px' } }
  const { font, pad } = SIZES[size] || SIZES.md
  const color = COLORS[tier] || COLORS.BRONZE

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: pad, borderRadius: 999, background: `${color}18`, border: `1px solid ${color}44`, fontSize: font, fontWeight: 800, letterSpacing: '0.12em', color }}>
      {ICONS[tier]} {tier}
    </span>
  )
}
