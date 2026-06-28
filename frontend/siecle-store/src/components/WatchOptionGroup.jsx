import WatchOptionButton from './WatchOptionButton'

export default function WatchOptionGroup({ groupKey, label, options, selectedId, onSelect }) {
  const selected = options.find(o => o.id === selectedId)
  return (
    <div className="watch-option-group">
      <p className="watch-option-group-title">
        {label.toUpperCase()}
        {selected && <span className="watch-option-group-selected">— {selected.label}</span>}
      </p>
      <div className="watch-option-grid">
        {options.map(opt => (
          <WatchOptionButton
            key={opt.id}
            option={opt}
            isActive={opt.id === selectedId}
            onSelect={(id) => onSelect(groupKey, id)}
          />
        ))}
      </div>
    </div>
  )
}
