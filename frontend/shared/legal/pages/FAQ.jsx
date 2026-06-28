import LegalLayout from '../LegalLayout'

const FAQS = {
  siecle: [
    {
      section: 'Commandes & Livraison',
      items: [
        {
          q: 'Quels sont les délais de livraison ?',
          a: 'Les commandes sont expédiées sous 2 à 3 jours ouvrés. La livraison standard prend 3 à 5 jours ouvrés en France métropolitaine. La livraison express est disponible à la commande.',
        },
        {
          q: 'Puis-je modifier ou annuler ma commande ?',
          a: 'Toute modification ou annulation doit être demandée dans les 2 heures suivant la commande via notre formulaire de contact. Passé ce délai, la commande est déjà en cours de préparation.',
        },
        {
          q: 'Livrez-vous à l\'international ?',
          a: 'Oui, nous livrons dans toute l\'Union Européenne. Les frais et délais varient selon le pays de destination. Contactez-nous pour les livraisons hors UE.',
        },
      ],
    },
    {
      section: 'Retours & Remboursements',
      items: [
        {
          q: 'Comment effectuer un retour ?',
          a: 'Vous disposez de 14 jours à compter de la réception pour retourner tout article non porté, dans son emballage d\'origine. Initiez votre retour depuis votre espace compte ou via notre service client.',
        },
        {
          q: 'Sous quel délai suis-je remboursé ?',
          a: 'Le remboursement est effectué dans les 5 à 7 jours ouvrés après réception et inspection du retour, sur le moyen de paiement original.',
        },
      ],
    },
    {
      section: 'Compte & Paiement',
      items: [
        {
          q: 'Quels moyens de paiement acceptez-vous ?',
          a: 'Nous acceptons les cartes bancaires (Visa, Mastercard, American Express) via Stripe, plateforme de paiement sécurisée. Vos données bancaires ne sont jamais stockées sur nos serveurs.',
        },
        {
          q: 'Mes données personnelles sont-elles sécurisées ?',
          a: 'Oui. Toutes les transactions sont chiffrées SSL. Nous ne partageons jamais vos données avec des tiers à des fins commerciales. Consultez notre politique de confidentialité pour en savoir plus.',
        },
        {
          q: 'J\'ai oublié mon mot de passe, que faire ?',
          a: 'Rendez-vous sur la page "Mot de passe oublié" depuis l\'écran de connexion. Un lien de réinitialisation valable 1 heure vous sera envoyé par email.',
        },
      ],
    },
    {
      section: 'Produits',
      items: [
        {
          q: 'Les éditions limitées sont-elles restockées ?',
          a: 'Non. Par définition, les éditions limitées SIÈCLE ne sont jamais restockées. Inscrivez-vous à notre liste d\'attente pour être informé des prochaines sorties.',
        },
        {
          q: 'Comment entretenir mes pièces SIÈCLE ?',
          a: 'Chaque produit est livré avec une fiche entretien spécifique. De manière générale, évitez l\'humidité, les produits chimiques et le stockage en lumière directe.',
        },
      ],
    },
  ],
  lunea: [
    {
      section: 'Commandes & Livraison',
      items: [
        {
          q: 'Quels sont les délais de livraison ?',
          a: 'Les commandes sont expédiées sous 2 à 3 jours ouvrés. La livraison standard prend 3 à 5 jours ouvrés en France métropolitaine.',
        },
        {
          q: 'Puis-je modifier ou annuler ma commande ?',
          a: 'Toute modification ou annulation doit être demandée dans les 2 heures suivant la commande via notre formulaire de contact.',
        },
      ],
    },
    {
      section: 'Retours & Remboursements',
      items: [
        {
          q: 'Puis-je retourner un produit cosmétique ?',
          a: 'Pour des raisons d\'hygiène, les produits cosmétiques ouverts ou utilisés ne sont pas repris. Les articles non ouverts et dans leur emballage d\'origine peuvent être retournés dans les 14 jours.',
        },
        {
          q: 'Sous quel délai suis-je remboursée ?',
          a: 'Le remboursement est effectué dans les 5 à 7 jours ouvrés après réception et inspection du retour.',
        },
      ],
    },
    {
      section: 'Produits & Conseils',
      items: [
        {
          q: 'Comment choisir les produits adaptés à ma peau ?',
          a: 'Notre outil de profil beauté analyse votre type de peau et vous recommande une routine personnalisée. Disponible dans votre espace compte.',
        },
        {
          q: 'Vos produits sont-ils testés sur les animaux ?',
          a: 'Non. Tous nos produits LUNEA sont formulés sans tests sur les animaux et sont conformes à la réglementation cosmétique européenne.',
        },
        {
          q: 'Quelle est la date de péremption de mes produits ?',
          a: 'La date d\'ouverture recommandée (PAO) est indiquée sur chaque emballage sous la forme d\'un pot ouvert avec le nombre de mois. Respectez cette durée après ouverture.',
        },
      ],
    },
    {
      section: 'Compte & Paiement',
      items: [
        {
          q: 'Quels moyens de paiement acceptez-vous ?',
          a: 'Nous acceptons les cartes bancaires via Stripe. Vos données bancaires ne sont jamais stockées sur nos serveurs.',
        },
        {
          q: 'J\'ai oublié mon mot de passe, que faire ?',
          a: 'Rendez-vous sur la page "Mot de passe oublié" depuis l\'écran de connexion. Un lien de réinitialisation valable 1 heure vous sera envoyé.',
        },
      ],
    },
  ],
}

function FAQSection({ section, items, brand }) {
  const accentColor = brand === 'lunea' ? '#c9a45c' : '#c9a96e'
  return (
    <div style={{ marginBottom: 48 }}>
      <h2 style={{ fontSize: 16, fontWeight: 800, letterSpacing: '0.1em', color: accentColor, marginBottom: 24, textTransform: 'uppercase' }}>
        {section}
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {items.map(({ q, a }, i) => (
          <FAQItem key={i} question={q} answer={a} brand={brand} last={i === items.length - 1} />
        ))}
      </div>
    </div>
  )
}

function FAQItem({ question, answer, brand, last }) {
  const borderColor = brand === 'lunea' ? 'rgba(201,164,92,0.15)' : 'rgba(255,255,255,0.07)'
  return (
    <div style={{
      borderBottom: last ? 'none' : `1px solid ${borderColor}`,
      padding: '20px 0',
    }}>
      <p style={{ fontWeight: 700, fontSize: 15, marginBottom: 10, lineHeight: 1.5 }}>{question}</p>
      <p style={{ fontSize: 14, lineHeight: 1.75, opacity: 0.75 }}>{answer}</p>
    </div>
  )
}

export default function FAQ({ brand = 'siecle' }) {
  const faqs = FAQS[brand] || FAQS.siecle
  return (
    <LegalLayout brand={brand} title="FAQ" subtitle="Questions fréquentes">
      {faqs.map(({ section, items }) => (
        <FAQSection key={section} section={section} items={items} brand={brand} />
      ))}
    </LegalLayout>
  )
}
