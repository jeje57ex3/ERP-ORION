/* Le bandeau des garanties, quatre colonnes. */
const SERVICES = [
  { glyph: '↗', name: 'Livraison rapide',  hint: 'Suivi de commande' },
  { glyph: '◇', name: 'Paiement sécurisé', hint: 'Transaction protégée' },
  { glyph: '↺', name: 'Retours simples',   hint: 'Selon nos conditions' },
  { glyph: '✳', name: 'Service client',    hint: 'À votre écoute' },
]

export default function Services() {
  return (
    <section className="sh-services" aria-label="Nos services">
      {SERVICES.map(s => (
        <div key={s.name} className="sh-service">
          <p className="sh-service__glyph" aria-hidden="true">{s.glyph}</p>
          <p className="sh-service__name">{s.name}</p>
          <p className="sh-service__hint">{s.hint}</p>
        </div>
      ))}
    </section>
  )
}
