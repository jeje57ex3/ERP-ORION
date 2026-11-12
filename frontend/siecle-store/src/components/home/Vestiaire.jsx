import { Link } from 'react-router-dom'
import ProductGrid from '../ProductGrid'

/* « COLLECTIONS PRINCIPALES / LE VESTIAIRE SIÈCLE ».
 *
 * Les pièces viennent du CATALOGUE DE L'ERP — c'est la plomberie qu'il
 * fallait garder intacte. Quand l'API ne répond pas ou que le catalogue est
 * vide, la section le dit au lieu de laisser un blanc qu'on prendrait pour
 * un défaut d'affichage. */
export default function Vestiaire({ products = [], loading = false }) {
  return (
    <section className="sh-section sh-rule" aria-label="Sélection SIÈCLE">
      <div className="sh-wrap">
        <div className="sh-vestiaire__head">
          <div>
            <p className="sh-eyebrow">Collections principales</p>
            <h2 className="sh-title sh-title--lg">Le vestiaire Siècle</h2>
            <p className="sh-lede">
              Les pièces essentielles et les ensembles coordonnés SIÈCLE,
              réunis dans le même vestiaire.
            </p>
          </div>
          <Link to="/boutique" className="sh-link">
            Voir toutes les pièces <span className="sh-link__arrow">↗</span>
          </Link>
        </div>

        {products.length > 0 ? (
          <ProductGrid products={products} columns={5} />
        ) : (
          <p className="sh-empty">
            {loading ? 'Chargement du vestiaire…' : 'Le vestiaire se remplit bientôt.'}
          </p>
        )}
      </div>
    </section>
  )
}
