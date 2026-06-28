import LegalLayout from '../LegalLayout'
import { LEGAL_CONFIG } from '../brandLegalConfig'

export default function LivraisonRetours({ brand = 'siecle' }) {
  const legal = LEGAL_CONFIG[brand]
  const isLunea = brand === 'lunea'

  return (
    <LegalLayout brand={brand} title="Livraison & retours">
      <p className="legal-note">
        Retrouvez ici les informations essentielles sur la préparation, la livraison et les retours.
      </p>

      <h2>Préparation des commandes</h2>
      <p>
        Les commandes sont préparées après validation du paiement. Le délai de préparation
        estimé est généralement de 2 à 5 jours ouvrés, sauf indication contraire sur la fiche produit.
      </p>

      <h2>Délais de livraison</h2>
      <p>
        Après expédition, le délai de livraison estimé est généralement de 3 à 7 jours ouvrés,
        selon la destination et le transporteur.
      </p>

      <h2>Frais de livraison</h2>
      <p>
        Les frais de livraison sont calculés lors du checkout avant validation du paiement.
        Une livraison offerte peut être proposée à partir d'un montant défini.
      </p>

      <h2>Zones livrées</h2>
      <p>
        Les zones de livraison disponibles sont indiquées au moment de la commande.
        Si une adresse n'est pas éligible, le client sera invité à choisir une autre adresse.
      </p>

      <h2>Suivi de commande</h2>
      <p>
        Lorsqu'un numéro de suivi est disponible, il est communiqué au client par email
        ou dans son espace client.
      </p>

      <h2>Retours</h2>
      <p>
        Pour demander un retour, le client doit contacter le service client à :{' '}
        <a href={`mailto:${legal.returnEmail}`}>{legal.returnEmail}</a>
      </p>

      <h2>Conditions de retour</h2>
      <ul>
        <li>Le produit doit être retourné dans son état d'origine.</li>
        <li>Le produit ne doit pas avoir été porté, utilisé, lavé ou détérioré.</li>
        <li>L'emballage, les accessoires et étiquettes doivent être conservés lorsque possible.</li>
        <li>Les produits personnalisés peuvent être exclus du retour.</li>
        {isLunea && (
          <li>
            Pour des raisons d'hygiène, les produits cosmétiques ouverts, descellés ou utilisés
            peuvent ne pas être repris.
          </li>
        )}
      </ul>

      <h2>Remboursement</h2>
      <p>
        Après réception et vérification du retour, le remboursement est effectué via le moyen
        de paiement utilisé lors de la commande, lorsque les conditions sont respectées.
      </p>
    </LegalLayout>
  )
}
