import './legal.css'

export default function LegalLayout({ brand = 'siecle', title, children }) {
  const brandClass = brand === 'lunea' ? 'legal-lunea' : 'legal-siecle'

  return (
    <main className={`legal-page ${brandClass}`}>
      <section className="legal-hero">
        <p>{brand === 'lunea' ? 'LUNEA' : 'SIÈCLE'}</p>
        <h1>{title}</h1>
      </section>

      <section className="legal-content">
        {children}
      </section>
    </main>
  )
}
