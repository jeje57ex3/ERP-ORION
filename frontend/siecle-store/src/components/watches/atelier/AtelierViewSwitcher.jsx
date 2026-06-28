const VIEWS = [
  { key: 'front', label: 'Face' },
  { key: 'side',  label: 'Profil' },
  { key: 'wrist', label: 'Poignet' },
  { key: 'back',  label: 'Dos' },
]

export default function AtelierViewSwitcher({ viewMode, setViewMode }) {
  return (
    <div className="atelier-view-switcher" role="group" aria-label="Vue de la montre">
      {VIEWS.map(v => (
        <button
          key={v.key}
          type="button"
          className={viewMode === v.key ? 'is-active' : ''}
          onClick={() => setViewMode(v.key)}
          aria-pressed={viewMode === v.key}
        >
          {v.label}
        </button>
      ))}
    </div>
  )
}
