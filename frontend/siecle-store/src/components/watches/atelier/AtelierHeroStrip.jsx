export default function AtelierHeroStrip({ model, price }) {
  const fmt = n => Number(n).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €'
  return (
    <div className="atelier-hero-strip">
      <div>
        <p className="atelier-kicker">Atelier SIÈCLE</p>
        <h1>{model.atelierName}</h1>
      </div>
      <div className="atelier-hero-center">
        <span>Composez votre montre signature.</span>
      </div>
      <div className="atelier-hero-price">{fmt(price.total)}</div>
    </div>
  )
}
