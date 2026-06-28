import { useEffect } from 'react'

export default function AtelierEngravingPanel({ group, engraving, updateEngraving, onAutoSwitchBack }) {
  useEffect(() => {
    if (engraving.enabled && onAutoSwitchBack) {
      onAutoSwitchBack('back')
    }
  }, [engraving.enabled])

  return (
    <section className="atelier-engraving-panel">
      <h3>Gravure personnelle</h3>
      <label className="atelier-toggle">
        <input
          type="checkbox"
          checked={engraving.enabled}
          onChange={e => updateEngraving({ enabled: e.target.checked })}
        />
        <span>Ajouter une gravure au dos</span>
      </label>

      {engraving.enabled && (
        <div className="atelier-engraving-fields">
          <input
            type="text"
            value={engraving.text}
            maxLength={group.maxLength}
            placeholder="Initiales, date ou phrase courte"
            onChange={e => updateEngraving({ text: e.target.value })}
          />
          <p className="atelier-engraving-count">
            {engraving.text.length}/{group.maxLength} caractères
          </p>
          <small className="atelier-engraving-hint">
            La vue dos prévisualise votre gravure en temps réel. +{group.priceDelta} €
          </small>
        </div>
      )}
    </section>
  )
}
