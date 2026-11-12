import { Link } from 'react-router-dom'

/* « LA SILHOUETTE DU MOMENT · 001 » — l'ensemble urbain.
 *
 * « product » est facultatif : fourni, son nom, son prix et son visuel
 * prennent la main sur le texte de référence, pour que la vitrine suive le
 * catalogue plutôt que de le contredire. */
export default function UrbanSet({ product }) {
  const prix = product?.price ?? '64,99'
  const lien = product?.slug ? `/product/${product.slug}` : '/boutique'
  const visuel = product?.image

  return (
    <section className="sh-urban" aria-label="La silhouette du moment">
      <div
        className="sh-urban__visual"
        style={visuel ? { backgroundImage: `url(${visuel})` } : undefined}
      >
        {!visuel && <span className="sh-urban__sigil">001</span>}
      </div>

      <div className="sh-urban__body">
        <p className="sh-eyebrow">Siècle / 001 · La silhouette du moment</p>
        <h2 className="sh-title sh-title--lg">
          {product?.name ?? 'Urban Set'}
          {!product && <span className="sh-accent">001.</span>}
        </h2>

        <ul className="sh-specs">
          <li>3 pièces</li>
          <li>Tailles S à 2XL</li>
          <li>Bandana inclus</li>
        </ul>

        <p className="sh-price">
          {prix}<span className="sh-price__cur">€</span>
        </p>

        <div className="sh-hero__actions">
          <Link to={lien} className="sh-btn sh-btn--gold">
            Découvrir la tenue <span className="sh-link__arrow">↗</span>
          </Link>
        </div>

        <p className="sh-note">Chemise + jean + bandana · un seul ensemble</p>
      </div>
    </section>
  )
}
