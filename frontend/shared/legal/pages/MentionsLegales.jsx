import LegalLayout from '../LegalLayout'
import { LEGAL_CONFIG } from '../brandLegalConfig'

export default function MentionsLegales({ brand = 'siecle' }) {
  const legal = LEGAL_CONFIG[brand]

  return (
    <LegalLayout brand={brand} title="Mentions légales">
      <p className="legal-note">
        Cette page présente les informations légales relatives au site {legal.brandName}.
      </p>

      <h2>Éditeur du site</h2>
      <p>
        Nom commercial : {legal.brandName}<br />
        Société : {legal.companyName}<br />
        Adresse : {legal.companyAddress}<br />
        SIRET : {legal.siret}<br />
        TVA intracommunautaire : {legal.vatNumber}<br />
        Directeur de la publication : {legal.publicationDirector}<br />
        Email : <a href={`mailto:${legal.supportEmail}`}>{legal.supportEmail}</a>
      </p>

      <h2>Hébergement</h2>
      <p>
        Hébergeur : {legal.hostingProvider}<br />
        Adresse : {legal.hostingAddress}
      </p>

      <h2>Propriété intellectuelle</h2>
      <p>
        Les contenus présents sur le site, incluant les textes, visuels, logos,
        photographies, éléments graphiques, interfaces et éléments de marque,
        sont protégés. Toute reproduction ou utilisation non autorisée est interdite.
      </p>

      <h2>Responsabilité</h2>
      <p>
        Le site met tout en œuvre pour fournir des informations exactes et à jour.
        Des erreurs ou indisponibilités peuvent toutefois survenir. L'utilisateur
        est invité à contacter le service client en cas de question.
      </p>

      <h2>Contact</h2>
      <p>
        Pour toute demande : <a href={`mailto:${legal.supportEmail}`}>{legal.supportEmail}</a>
      </p>
    </LegalLayout>
  )
}
