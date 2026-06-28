export default function WatchOptionButton({ option, isActive, onSelect }) {
  const delta = option.priceDelta
  return (
    <button
      className={`watch-option-button${isActive ? ' active' : ''}`}
      onClick={() => onSelect(option.id)}
      title={option.label}
      type="button"
    >
      <span className="watch-color-dot" style={{ background: option.color }} />
      <span className="watch-option-label">{option.label}</span>
      {delta > 0 && <span className="watch-option-delta">+{delta} €</span>}
    </button>
  )
}
