import { Link } from 'react-router-dom'

/* « NOUVELLE COLLECTION / L'AVENIR S'HABILLE AUJOURD'HUI. » */
export default function NewCollection() {
  return (
    <section className="sh-section" aria-label="Nouvelle collection">
      <div className="sh-wrap sh-center">
        <p className="sh-eyebrow">Nouvelle collection</p>
        <h2 className="sh-title sh-title--md">L’avenir s’habille aujourd’hui.</h2>
        <p className="sh-lede">Une nouvelle silhouette. Une même vision.</p>
        <p style={{ marginTop: 34 }}>
          <Link to="/drops" className="sh-btn">
            Découvrir le drop <span className="sh-link__arrow">↗</span>
          </Link>
        </p>
      </div>
    </section>
  )
}
