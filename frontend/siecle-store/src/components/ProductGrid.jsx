import ProductCard from './ProductCard'

export default function ProductGrid({ products = [], columns = 4 }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${columns}, 1fr)`,
      gap: '32px 24px',
    }}
      className={`siecle-product-grid siecle-grid-${columns}`}
    >
      {products.map((p, i) => (
        <ProductCard key={p.id || p.slug} product={p} index={i} />
      ))}
      <style>{`
        @media (max-width: 1024px) {
          .siecle-grid-4 { grid-template-columns: repeat(3, 1fr) !important; }
        }
        @media (max-width: 768px) {
          .siecle-product-grid { grid-template-columns: repeat(2, 1fr) !important; gap: 20px 12px !important; }
        }
        @media (max-width: 480px) {
          .siecle-product-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}
