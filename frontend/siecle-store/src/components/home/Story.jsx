import { Link } from 'react-router-dom'

/* « NOTRE HISTOIRE / UN SIÈCLE D'AVANCE. » */
export default function Story({ image }) {
  return (
    <section className="sh-section" aria-label="L’univers SIÈCLE">
      <div className="sh-wrap sh-story">
        <div>
          <p className="sh-eyebrow">Notre histoire</p>
          <h2 className="sh-title sh-title--lg">Un siècle d’avance.</h2>
          <p className="sh-lede">
            Une vision contemporaine entre l’élégance italienne et la culture
            urbaine.
          </p>
          <p style={{ marginTop: 34 }}>
            <Link to="/maison-siecle" className="sh-link">
              Découvrir <span className="sh-link__arrow">↗</span>
            </Link>
          </p>
        </div>

        <div
          className="sh-story__visual"
          style={image ? { backgroundImage: `url(${image})` } : undefined}
        >
          {!image && <span className="sh-urban__sigil">S</span>}
        </div>
      </div>
    </section>
  )
}
