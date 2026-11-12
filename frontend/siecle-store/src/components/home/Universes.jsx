import { Link } from 'react-router-dom'

/* Les quatre univers, dans l'ordre et avec les accroches du site. */
export const UNIVERS = [
  { num: '01', tag: 'Rue. Élégance. Vision.', name: 'Streetwear',  to: '/vetements' },
  { num: '02', tag: 'Alta Sartoria Italiana', name: 'Costumes',    to: '/vetements?categorie=tailleur' },
  { num: '03', tag: 'Détails qui comptent',   name: 'Accessoires', to: '/boutique?category=accessoires' },
  { num: '04', tag: 'Maison horlogère',       name: 'Montres',     to: '/montres' },
]

export default function Universes({ items = UNIVERS }) {
  return (
    <section className="sh-universes" aria-label="Les univers SIÈCLE">
      {items.map(u => (
        <Link key={u.num} to={u.to} className="sh-universe">
          <span className="sh-universe__num">{u.num}</span>
          <span className="sh-universe__arrow" aria-hidden="true">↗</span>
          <p className="sh-universe__tag">{u.tag}</p>
          <h3 className="sh-universe__name">{u.name}</h3>
        </Link>
      ))}
    </section>
  )
}
