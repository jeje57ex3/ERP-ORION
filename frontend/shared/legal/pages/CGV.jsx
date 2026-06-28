import LegalLayout from '../LegalLayout'
import { LEGAL_CONFIG } from '../brandLegalConfig'

export default function CGV({ brand = 'siecle' }) {
  const legal = LEGAL_CONFIG[brand]

  return (
    <LegalLayout brand={brand} title="Conditions générales de vente">
      <p className="legal-note">
        Les présentes conditions générales de vente s'appliquent aux commandes passées sur le site {legal.brandName}.
      </p>

      <h2>Produits</h2>
      <p>
        Les produits proposés sont décrits avec le plus grand soin. Les visuels peuvent
        présenter de légères différences selon les écrans, les matières, les finitions
        ou les lots de fabrication.
      </p>

      <h2>Prix</h2>
      <p>
        Les prix sont affichés en euros. Le montant total est indiqué avant validation
        de la commande, incluant les éventuels frais de livraison applicables.
      </p>

      <h2>Commande</h2>
      <p>
        Le client vérifie le contenu de son panier avant paiement. La commande est
        confirmée après validation du paiement.
      </p>

      <h2>Paiement</h2>
      <p>
        Le paiement est sécurisé et traité par Stripe. La commande peut être refusée
        en cas d'échec, d'annulation ou de suspicion de fraude.
      </p>

      <h2>Livraison</h2>
      <p>
        Les délais de préparation et de livraison sont indiqués sur la page Livraison & retours.
        Ils peuvent varier selon les périodes, les produits et les transporteurs.
      </p>

      <h2>Droit de rétractation et retours</h2>
      <p>
        Le client dispose d'un délai légal de rétractation lorsque celui-ci est applicable.
        Certains produits peuvent être exclus du retour pour des raisons d'hygiène,
        de personnalisation ou lorsqu'ils ont été descellés ou utilisés.
      </p>

      <h2>Produits indisponibles</h2>
      <p>
        En cas d'indisponibilité après commande, le client sera informé et une solution
        sera proposée : attente, remplacement, avoir ou remboursement.
      </p>

      <h2>Service client</h2>
      <p>
        Pour toute question : <a href={`mailto:${legal.supportEmail}`}>{legal.supportEmail}</a>
      </p>
    </LegalLayout>
  )
}
