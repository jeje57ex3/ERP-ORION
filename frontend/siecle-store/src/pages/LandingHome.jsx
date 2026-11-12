import { useEffect, useState } from 'react'
import { Helmet } from 'react-helmet-async'

import UniverseBar from '../components/home/UniverseBar'
import BrandHero from '../components/home/BrandHero'
import Universes, { UNIVERS } from '../components/home/Universes'
import Vestiaire from '../components/home/Vestiaire'
import UrbanSet from '../components/home/UrbanSet'
import ChampionDrop from '../components/home/ChampionDrop'
import Styling from '../components/home/Styling'
import Story from '../components/home/Story'
import Manifesto from '../components/home/Manifesto'
import NewCollection from '../components/home/NewCollection'
import Services from '../components/home/Services'
import NewsletterSection from '../components/NewsletterSection'

import { getProducts } from '../api/products'
import '../styles/siecle-home.css'

/* LA PAGE D'ACCUEIL SIÈCLE, REPRISE DE siecle.shop
 *
 * CE QUI A CHANGÉ, ET CE QUI N'A PAS BOUGÉ
 *
 * L'habillage est remplacé ; la plomberie de données ne l'est pas. Les
 * pièces affichées viennent toujours de « getProducts », donc du catalogue
 * de l'ERP : produits, clients et COMMANDES sont intacts. C'était la
 * condition posée, et c'est aussi la raison pour laquelle rien n'a été
 * supprimé côté Django.
 *
 * L'ORDRE DES SECTIONS EST CELUI DU SITE DE RÉFÉRENCE
 *
 * Bandeau des univers, campagne, les quatre univers, le vestiaire, la
 * silhouette 001, la précommande Champion, le stylisme, l'histoire, le
 * manifeste, la nouvelle collection, les garanties.
 *
 * DEUX ÉCARTS ASSUMÉS, PLUTÔT QUE SILENCIEUX
 *
 * — « InstagramCommunity » est retiré : le site de référence n'a pas cette
 *   section, et elle n'était que décorative.
 * — « NewsletterSection » est CONSERVÉ bien qu'absent de la référence. Ce
 *   bloc collecte des adresses ; le retirer au nom du dessin ferait perdre
 *   des inscriptions sans que personne s'en aperçoive. Si l'habillage doit
 *   primer, c'est une ligne à supprimer — mais ce doit être un choix, pas
 *   un effet de bord.
 */

/* Le site de référence met cinq pièces dans le vestiaire. */
const PIECES_AU_VESTIAIRE = 5

/* Deux sections ont leur produit vedette. On le reconnaît dans la sélection
   déjà chargée plutôt qu'en relançant une requête : la vitrine suit alors
   le catalogue, et sans un appel de plus. */
const trouver = (produits, fragments) => produits.find(p => {
  const nom = (p?.name || '').toLowerCase()
  return fragments.some(f => nom.includes(f))
})

export default function LandingHome() {
  const [pieces, setPieces] = useState([])
  const [chargement, setChargement] = useState(true)

  useEffect(() => {
    let vivant = true

    getProducts({ featured: true, limit: PIECES_AU_VESTIAIRE })
      .then(d => { if (vivant) setPieces((d.results || []).slice(0, PIECES_AU_VESTIAIRE)) })
      // Un catalogue injoignable ne doit pas laisser la page en
      // « Chargement… » indéfiniment : on relâche l'état dans tous les cas.
      .catch(() => {})
      .finally(() => { if (vivant) setChargement(false) })

    return () => { vivant = false }
  }, [])

  return (
    <div className="sh-page">
      <Helmet>
        <title>SIÈCLE — Une vision. Plusieurs expressions.</title>
        <meta
          name="description"
          content="SIÈCLE, Paris. Streetwear, costumes italiens, accessoires et
                   montres : une vision contemporaine entre l'élégance italienne
                   et la culture urbaine."
        />
      </Helmet>

      <UniverseBar count={UNIVERS.length} />
      <BrandHero />
      <Universes />

      <Vestiaire products={pieces} loading={chargement} />

      <UrbanSet product={trouver(pieces, ['urban set', 'urban'])} />
      <ChampionDrop product={trouver(pieces, ['packable', 'champion'])} />

      <Styling />
      <Story />
      <Manifesto />
      <NewCollection />

      <NewsletterSection />
      <Services />
    </div>
  )
}
