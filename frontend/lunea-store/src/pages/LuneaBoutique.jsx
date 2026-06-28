import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

export default function LuneaBoutique() {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    document.title = 'Boutique — LUNEA'
    fetch('/api/v1/lunea/products/?limit=24')
      .then(r => r.json())
      .then(d => setProducts(d.results ?? []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      <section className="lunea-section">
        <div className="lunea-container">
          <p className="lunea-eyebrow">Boutique</p>
          <h1 className="lunea-heading" style={{ marginBottom: '2.5rem' }}>Tous nos produits</h1>

          {loading ? (
            <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--color-text-muted)' }}>
              Chargement...
            </div>
          ) : products.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--color-text-muted)' }}>
              <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.2rem', marginBottom: '0.5rem' }}>
                Catalogue en cours de chargement
              </p>
              <p style={{ fontSize: 13 }}>Nos produits arrivent bientôt.</p>
            </div>
          ) : (
            <div className="lunea-product-grid">
              {products.map(p => (
                <Link key={p.id} to={`/lunea/produit/${p.slug}/`} style={{ textDecoration: 'none', color: 'inherit' }} className="lunea-product-card">
                  <div className="lunea-product-card__image">
                    {p.image
                      ? <img src={p.image} alt={p.name} loading="lazy" />
                      : <div style={{ width: '100%', height: '100%', background: 'var(--color-border)' }} />
                    }
                  </div>
                  <div className="lunea-product-card__body">
                    <p className="lunea-product-card__name">{p.name}</p>
                    <p className="lunea-product-card__price">
                      {Number(p.price || 0).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
