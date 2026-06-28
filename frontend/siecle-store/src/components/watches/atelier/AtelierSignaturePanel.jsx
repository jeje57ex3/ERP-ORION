import { useState } from 'react'
import AtelierHarmonieScore from './AtelierHarmonieScore'
import AtelierStoryText from './AtelierStoryText'
import { saveWatchAtelier } from '../../../api/watches'

const fmt = n => Number(n).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'

export default function AtelierSignaturePanel({ configuration, updateConfiguration, price, harmonyScore, story }) {
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [shareUrl, setShareUrl] = useState('')

  async function handleSave() {
    setSaving(true)
    setSaveMsg('')
    try {
      const res = await saveWatchAtelier({
        name: configuration.creationName,
        configuration,
        base_price: price.basePrice,
        options_price: price.total - price.basePrice,
        total_price: price.total,
        harmony_score: harmonyScore,
        story,
      })
      if (res.share_token) {
        const url = `${window.location.origin}/montres/atelier/?config=${res.share_token}`
        setShareUrl(url)
        setSaveMsg('Création sauvegardée.')
      }
    } catch {
      setSaveMsg('Connexion requise pour sauvegarder.')
    } finally {
      setSaving(false)
    }
  }

  function handleShare() {
    if (shareUrl) {
      navigator.clipboard?.writeText(shareUrl).then(() => setSaveMsg('Lien copié !'))
    } else {
      handleSave()
    }
  }

  const optionsDelta = price.total - price.basePrice
  const loyaltyPoints = Math.floor(price.total * 0.05)

  return (
    <aside className="atelier-signature-panel">
      <p className="atelier-kicker">Votre signature</p>

      <input
        className="atelier-creation-name"
        value={configuration.creationName}
        onChange={e => updateConfiguration('creationName', e.target.value)}
        placeholder="Nommez votre création..."
        aria-label="Nom de votre création"
      />

      <AtelierHarmonieScore score={harmonyScore} />
      <AtelierStoryText story={story} />

      <div className="atelier-signature-breakdown">
        <div className="atelier-signature-breakdown__row">
          <span>Modèle de base</span>
          <span>{fmt(price.basePrice)}</span>
        </div>
        {optionsDelta > 0 && (
          <div className="atelier-signature-breakdown__row">
            <span>Options</span>
            <span>+{fmt(optionsDelta)}</span>
          </div>
        )}
        {configuration.engraving?.enabled && configuration.engraving?.text && (
          <div className="atelier-signature-breakdown__row">
            <span>Gravure</span>
            <span>+25,00 €</span>
          </div>
        )}
      </div>

      <div className="atelier-signature-price">
        <span>Total</span>
        <strong>{fmt(price.total)}</strong>
      </div>

      <div className="atelier-loyalty-hint">
        <span>+{loyaltyPoints} pts SIÈCLE</span>
      </div>

      {saveMsg && <p className="atelier-save-msg">{saveMsg}</p>}

      <div className="atelier-signature-actions">
        <button type="button" onClick={handleSave} disabled={saving} className="atelier-btn-save">
          {saving ? 'Sauvegarde...' : 'Sauvegarder'}
        </button>
        <button type="button" onClick={handleShare} className="atelier-btn-share">
          Partager
        </button>
      </div>
    </aside>
  )
}
