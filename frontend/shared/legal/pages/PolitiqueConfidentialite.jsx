import LegalLayout from '../LegalLayout'
import { LEGAL_CONFIG } from '../brandLegalConfig'

export default function PolitiqueConfidentialite({ brand = 'siecle' }) {
  const legal = LEGAL_CONFIG[brand]

  return (
    <LegalLayout brand={brand} title="Politique de confidentialité">
      <p className="legal-note">
        Cette politique explique comment {legal.brandName} collecte et utilise les données personnelles.
      </p>

      <h2>Données collectées</h2>
      <p>
        Nous pouvons collecter les informations nécessaires à la gestion des commandes,
        des comptes clients, du paiement, de la livraison, du service client et de la sécurité.
      </p>
      <ul>
        <li>Identité : nom, prénom</li>
        <li>Coordonnées : email, téléphone, adresses de livraison et facturation</li>
        <li>Données de commande : produits, montants, statuts</li>
        <li>Données de compte : identifiants, préférences, historique</li>
        <li>Données techniques : adresse IP, navigateur, logs de sécurité</li>
      </ul>

      <h2>Finalités</h2>
      <p>
        Les données sont utilisées pour traiter les commandes, gérer les paiements,
        assurer la livraison, répondre aux demandes, sécuriser le site, respecter
        les obligations légales et améliorer l'expérience client.
      </p>

      <h2>Paiement</h2>
      <p>
        Les paiements sont traités par Stripe. Les données bancaires complètes ne
        sont pas stockées par {legal.brandName}.
      </p>

      <h2>Durée de conservation</h2>
      <p>
        Les données sont conservées pendant la durée nécessaire aux finalités indiquées,
        ainsi que pour respecter les obligations comptables, fiscales et légales.
      </p>

      <h2>Droits des utilisateurs</h2>
      <p>
        Vous pouvez demander l'accès, la rectification ou la suppression de vos données,
        dans les limites prévues par la loi.
      </p>

      <h2>Contact</h2>
      <p>
        Pour toute demande relative à vos données : <a href={`mailto:${legal.supportEmail}`}>{legal.supportEmail}</a>
      </p>
    </LegalLayout>
  )
}
