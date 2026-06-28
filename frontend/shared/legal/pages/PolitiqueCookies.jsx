import LegalLayout from '../LegalLayout'
import { LEGAL_CONFIG } from '../brandLegalConfig'

export default function PolitiqueCookies({ brand = 'siecle' }) {
  const legal = LEGAL_CONFIG[brand]

  return (
    <LegalLayout brand={brand} title="Politique cookies">
      <p>
        Le site {legal.brandName} peut utiliser des cookies nécessaires au bon fonctionnement
        du site, ainsi que des cookies de mesure d'audience ou marketing si l'utilisateur y consent.
      </p>

      <h2>Cookies nécessaires</h2>
      <p>
        Ces cookies permettent le fonctionnement du panier, du compte client, du checkout
        et de la sécurité. Ils ne peuvent pas être désactivés depuis le site.
      </p>

      <h2>Cookies optionnels</h2>
      <p>
        Les cookies de mesure d'audience ou de publicité ne doivent être activés qu'après
        consentement si des outils comme Google Analytics ou Meta Pixel sont utilisés.
      </p>

      <h2>Gestion du consentement</h2>
      <p>
        L'utilisateur peut accepter, refuser ou modifier ses préférences lorsque la bannière
        cookies est activée.
      </p>

      <h2>Contact</h2>
      <p>
        Pour toute question : <a href={`mailto:${legal.supportEmail}`}>{legal.supportEmail}</a>
      </p>
    </LegalLayout>
  )
}
