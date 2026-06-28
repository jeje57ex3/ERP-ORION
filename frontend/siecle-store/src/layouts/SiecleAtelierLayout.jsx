import { Link } from 'react-router-dom'
import Header from '../components/Header'
import '../styles/siecle-atelier-layout.css'

export default function SiecleAtelierLayout({ children }) {
  return (
    <div className="siecle-atelier-layout">
      <Header />
      <div className="siecle-atelier-exit">
        <Link to="/montres" className="siecle-atelier-exit__btn">
          ← Quitter l'Atelier
        </Link>
      </div>
      <main className="siecle-atelier-main">
        {children}
      </main>
    </div>
  )
}
