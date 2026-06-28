import AtelierOptionTile from './AtelierOptionTile'

export default function AtelierOptionGroup({ group, selectedValue, onChange }) {
  return (
    <section className="atelier-option-group">
      <div className="atelier-option-group-header">
        <h3>{group.title}</h3>
      </div>
      <div className={`atelier-option-grid atelier-option-grid-${group.type}`}>
        {group.options.map(option => (
          <AtelierOptionTile
            key={option.id}
            option={option}
            type={group.type}
            isSelected={option.id === selectedValue}
            onClick={() => onChange(option.id)}
          />
        ))}
      </div>
    </section>
  )
}
