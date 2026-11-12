import { Link } from 'react-router-dom'

/* « PRÉCOMMANDE · DROP 001 » — la veste packable SIÈCLE × CHAMPION. */
export default function ChampionDrop({ product }) {
  const prix = product?.price ?? '68'
  const lien = product?.slug ? `/product/${product.slug}` : '/drops'

  return (
    <section className="sh-drop" aria-label="Précommande drop 001">
      <div className="sh-wrap">
        <p className="sh-eyebrow">Précommande · Drop 001</p>
        <h2 className="sh-title sh-title--xl">
          Packable
          <span className="sh-accent">Jacket</span>
        </h2>
        <p className="sh-drop__x">Siècle × Champion</p>
        <p className="sh-lede sh-center">
          Une silhouette noire, légère et déperlante.
        </p>

        <p className="sh-price" style={{ justifyContent: 'center' }}>
          {prix}<span className="sh-price__cur">€</span>
        </p>

        <div className="sh-drop__actions">
          <Link to={lien} className="sh-btn">
            Précommander <span className="sh-link__arrow">↗</span>
          </Link>
        </div>
      </div>
    </section>
  )
}
