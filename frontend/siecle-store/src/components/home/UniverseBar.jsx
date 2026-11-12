import { Link } from 'react-router-dom'

/* Le bandeau de tête : « EXPLORER LES UNIVERS 001 — 004 ». Le compte est
   DÉDUIT du nombre d'univers, pas écrit en dur : ajouter un univers sans
   corriger le bandeau donnerait un site qui se contredit lui-même. */
export default function UniverseBar({ count = 4, to = '/univers' }) {
  const fin = String(count).padStart(3, '0')

  return (
    <Link to={to} className="sh-bar">
      <span>Explorer les univers</span>
      <span className="sh-bar__count">001 — {fin}</span>
    </Link>
  )
}
