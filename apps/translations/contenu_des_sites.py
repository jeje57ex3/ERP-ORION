# -*- coding: utf-8 -*-
"""Les traductions du contenu STATIQUE des sites publics.

POURQUOI CE MODULE EXISTE, ET POURQUOI C'EST UNE CORRECTION DE LIVRAISON

Les noms de services et la foire aux questions des vitrines ne viennent
pas de la base : ce sont des listes Python, dans
`apps/websites/electricite_public_views.py` et `btp_public_views.py`. Elles
passent par `translate_static_items`, qui lit `InterfaceTranslation` — donc
la BASE — et retombe sur le français quand aucune ligne n'existe.

Or rien ne créait ces lignes, sinon
`manage.py seed_site_translations`, un fichier QUI N'ÉTAIT PAS SUIVI PAR
GIT. Il n'existait donc pas sur le serveur, et c'était une commande en
terminal, ce que les règles de ce projet interdisent pour un réglage
d'exploitation. Résultat mesuré : sur le site en service, les noms de
services et la FAQ — l'essentiel du contenu visible d'une page d'accueil —
restaient en français DANS TOUTES LES LANGUES, et rien ne le signalait
puisqu'une traduction absente retombe sur la source.

Les données sont donc ici, dans un module versionné, et une migration de
données les pose. Elle passe à chaque mise à jour, sans qu'on ouvre un
terminal.

L'ALLEMAND N'Y ÉTAIT PAS. La commande portait en/es/it/pt. Il est ajouté.

LE FRANÇAIS N'EST PAS DÉCLARÉ, volontairement : il est la source, dans le
code des vues. `get_translation` retombe sur le texte fourni par la vue
quand aucune traduction n'existe, donc le français s'affiche tel quel.
Déclarer des lignes « fr » dupliquerait la source et les deux finiraient
par diverger.
"""

#: clé -> {code de langue: texte}. Le français est absent, voir ci-dessus.
TRADUCTIONS_DES_SITES = {
    'btp.work.chauffage.desc': {
        'en': 'Boilers, heat pumps, radiators, underfloor heating.',
        'es': 'Calderas, bombas de calor, radiadores, suelo radiante.',
        'it': 'Caldaie, pompe di calore, radiatori, riscaldamento a pavimento.',
        'pt': 'Caldeiras, bombas de calor, radiadores, piso radiante.',
        'de': 'Heizkessel, Wärmepumpen, Heizkörper, Fußbodenheizung.',
    },
    'btp.work.chauffage.name': {
        'en': 'Heating',
        'es': 'Calefacción',
        'it': 'Riscaldamento',
        'pt': 'Aquecimento',
        'de': 'Heizung',
    },
    'btp.work.cuisine.desc': {
        'en': 'Fitted kitchen installation, worktop, appliances.',
        'es': 'Instalación de cocina equipada, encimera, electrodomésticos.',
        'it': 'Installazione cucina componibile, piano di lavoro, elettrodomestici.',
        'pt': 'Instalação de cozinha equipada, bancada, eletrodomésticos.',
        'de': 'Einbau von Einbauküchen, Arbeitsplatten und Geräten.',
    },
    'btp.work.cuisine.name': {
        'en': 'Kitchen',
        'es': 'Cocina',
        'it': 'Cucina',
        'pt': 'Cozinha',
        'de': 'Küche',
    },
    'btp.work.electricite.desc': {
        'en': 'Installation, compliance upgrades, electrical repairs.',
        'es': 'Instalación, puesta en conformidad, reparación eléctrica.',
        'it': 'Installazione, messa a norma, riparazione elettrica.',
        'pt': 'Instalação, adequação às normas, reparação elétrica.',
        'de': 'Installation, Normanpassung, Elektroreparaturen.',
    },
    'btp.work.electricite.name': {
        'en': 'Electrical',
        'es': 'Electricidad',
        'it': 'Elettricità',
        'pt': 'Eletricidade',
        'de': 'Elektrik',
    },
    'btp.work.extension.desc': {
        'en': 'Extension, veranda, additional storey.',
        'es': 'Ampliación, porche acristalado, elevación.',
        'it': 'Ampliamento, veranda, sopraelevazione.',
        'pt': 'Ampliação, marquise, sobrelevação.',
        'de': 'Anbau, Wintergarten, zusätzliches Geschoss.',
    },
    'btp.work.extension.name': {
        'en': 'Extension',
        'es': 'Ampliación',
        'it': 'Ampliamento',
        'pt': 'Ampliação',
        'de': 'Anbau',
    },
    'btp.work.isolation.desc': {
        'en': 'Attic, wall and façade insulation — energy efficiency.',
        'es': 'Aislamiento de buhardillas, muros, fachada — eficiencia energética.',
        'it': 'Isolamento di sottotetti, muri, facciata — efficienza energetica.',
        'pt': 'Isolamento de sótãos, paredes, fachada — eficiência energética.',
        'de': 'Dach-, Wand- und Fassadendämmung – Energieeffizienz.',
    },
    'btp.work.isolation.name': {
        'en': 'Insulation',
        'es': 'Aislamiento',
        'it': 'Isolamento',
        'pt': 'Isolamento',
        'de': 'Dämmung',
    },
    'btp.work.maconnerie.desc': {
        'en': 'Structural work, slabs, foundations, walls.',
        'es': 'Obra gruesa, losas, cimentaciones, muros.',
        'it': 'Opere strutturali, solette, fondazioni, muri.',
        'pt': 'Obra bruta, lajes, fundações, paredes.',
        'de': 'Rohbau, Bodenplatten, Fundamente, Wände.',
    },
    'btp.work.maconnerie.name': {
        'en': 'Masonry',
        'es': 'Albañilería',
        'it': 'Muratura',
        'pt': 'Alvenaria',
        'de': 'Mauerwerk',
    },
    'btp.work.menuiserie.desc': {
        'en': 'Windows, doors, flooring, wood fittings.',
        'es': 'Ventanas, puertas, parqué, carpintería a medida.',
        'it': 'Finestre, porte, parquet, arredi in legno.',
        'pt': 'Janelas, portas, pavimento, mobiliário em madeira.',
        'de': 'Fenster, Türen, Bodenbeläge, Holzeinbauten.',
    },
    'btp.work.menuiserie.name': {
        'en': 'Joinery',
        'es': 'Carpintería',
        'it': 'Falegnameria',
        'pt': 'Carpintaria',
        'de': 'Schreinerarbeiten',
    },
    'btp.work.peinture.desc': {
        'en': 'Rendering, interior / exterior painting.',
        'es': 'Revoques, pintura interior / exterior.',
        'it': 'Intonaci, pittura interna / esterna.',
        'pt': 'Rebocos, pintura interior / exterior.',
        'de': 'Verputz, Innen- und Außenanstrich.',
    },
    'btp.work.peinture.name': {
        'en': 'Painting',
        'es': 'Pintura',
        'it': 'Pittura',
        'pt': 'Pintura',
        'de': 'Malerarbeiten',
    },
    'btp.work.plomberie.desc': {
        'en': 'Piping, sanitary ware, water leaks, water heaters.',
        'es': 'Tuberías, sanitarios, fugas de agua, calentadores.',
        'it': "Tubature, sanitari, perdite d'acqua, scaldabagni.",
        'pt': 'Tubagens, sanitários, fugas de água, esquentadores.',
        'de': 'Rohrleitungen, Sanitärobjekte, Wasserschäden, Warmwasserbereiter.',
    },
    'btp.work.plomberie.name': {
        'en': 'Plumbing',
        'es': 'Fontanería',
        'it': 'Idraulica',
        'pt': 'Canalização',
        'de': 'Sanitärinstallation',
    },
    'btp.work.renovation-complete.desc': {
        'en': 'Coordination of all trades.',
        'es': 'Coordinación de todos los oficios.',
        'it': 'Coordinamento di tutte le maestranze.',
        'pt': 'Coordenação de todas as especialidades.',
        'de': 'Koordination aller Gewerke.',
    },
    'btp.work.renovation-complete.name': {
        'en': 'Full renovation',
        'es': 'Reforma integral',
        'it': 'Ristrutturazione completa',
        'pt': 'Renovação completa',
        'de': 'Komplettsanierung',
    },
    'btp.work.revetement-sol.desc': {
        'en': 'Tiling, parquet, laminate, carpet.',
        'es': 'Baldosas, parqué, laminado, moqueta.',
        'it': 'Piastrelle, parquet, laminato, moquette.',
        'pt': 'Ladrilhos, parquet, laminado, alcatifa.',
        'de': 'Fliesen, Parkett, Laminat, Teppichboden.',
    },
    'btp.work.revetement-sol.name': {
        'en': 'Flooring',
        'es': 'Revestimiento de suelos',
        'it': 'Rivestimento pavimenti',
        'pt': 'Revestimento de pavimentos',
        'de': 'Bodenbeläge',
    },
    'btp.work.salle-de-bain.desc': {
        'en': 'Full renovation, shower, bathtub, WC.',
        'es': 'Renovación completa, ducha, bañera, WC.',
        'it': 'Ristrutturazione completa, doccia, vasca, WC.',
        'pt': 'Renovação completa, duche, banheira, sanita.',
        'de': 'Komplettsanierung, Dusche, Badewanne, WC.',
    },
    'btp.work.salle-de-bain.name': {
        'en': 'Bathroom',
        'es': 'Cuarto de baño',
        'it': 'Bagno',
        'pt': 'Casa de banho',
        'de': 'Badezimmer',
    },
    'btp.work.toiture.desc': {
        'en': 'Roof covering, flashing, roof maintenance.',
        'es': 'Cubierta, chapistería, mantenimiento de tejados.',
        'it': 'Copertura, lattoneria, manutenzione del tetto.',
        'pt': 'Cobertura, chapeamento, manutenção de telhados.',
        'de': 'Dacheindeckung, Abdichtungen, Dachwartung.',
    },
    'btp.work.toiture.name': {
        'en': 'Roofing',
        'es': 'Tejado',
        'it': 'Copertura',
        'pt': 'Cobertura',
        'de': 'Dacharbeiten',
    },
    'electricite.faq.0.answer': {
        'en': 'The cost depends on the surface area, the condition of the existing installation and the quality level chosen. Use our configurator for an instant pre-quote.',
        'es': 'El coste depende de la superficie, el estado de la instalación existente y el nivel de gama elegido. Utilice nuestro configurador para obtener un presupuesto instantáneo.',
        'it': "Il costo dipende dalla superficie, dallo stato dell'impianto esistente e dal livello di gamma scelto. Usa il nostro configuratore per un preventivo istantaneo.",
        'pt': 'O custo depende da área, do estado da instalação existente e do nível de gama escolhido. Utilize o nosso configurador para obter um pré-orçamento instantâneo.',
        'de': 'Die Kosten hängen von der Fläche, dem Zustand der bestehenden Anlage und der gewählten Ausstattungsklasse ab. Nutzen Sie unseren Konfigurator für ein sofortiges Vorabangebot.',
    },
    'electricite.faq.0.question': {
        'en': 'How much does an electrical compliance upgrade cost?',
        'es': '¿Cuánto cuesta una puesta en conformidad eléctrica?',
        'it': 'Quanto costa una messa a norma elettrica?',
        'pt': 'Quanto custa uma adequação elétrica às normas?',
        'de': 'Was kostet eine elektrische Normanpassung?',
    },
    'electricite.faq.1.answer': {
        'en': 'Yes, our emergency service handles electrical emergencies (total power loss, burning smell, sparks) as a priority — use the emergency configurator.',
        'es': 'Sí, nuestro servicio de urgencias atiende con prioridad las emergencias eléctricas (corte total, olor a quemado, chispas) — utilice el configurador de urgencias.',
        'it': 'Sì, il nostro servizio guasti tratta con priorità le emergenze elettriche (blackout totale, odore di bruciato, scintille) — usa il configuratore di emergenza.',
        'pt': 'Sim, o nosso serviço de urgência trata com prioridade as emergências elétricas (corte total, cheiro a queimado, faíscas) — utilize o configurador de urgência.',
        'de': 'Ja, unser Notdienst behandelt elektrische Notfälle (Totalausfall, Brandgeruch, Funkenbildung) vorrangig – nutzen Sie den Notfall-Konfigurator.',
    },
    'electricite.faq.1.question': {
        'en': 'Do you offer emergency call-outs?',
        'es': '¿Atienden urgencias?',
        'it': 'Intervenite in caso di urgenza?',
        'pt': 'Atendem urgências?',
        'de': 'Übernehmen Sie Noteinsätze?',
    },
    'electricite.faq.2.answer': {
        'en': 'Yes, contracts with scheduled periodic visits and priority call-out are available — contact us for a tailored quote.',
        'es': 'Sí, disponemos de contratos con visitas periódicas programadas y prioridad de intervención — contáctenos para un presupuesto personalizado.',
        'it': 'Sì, sono disponibili contratti con visite periodiche programmate e priorità di intervento — contattaci per un preventivo personalizzato.',
        'pt': 'Sim, estão disponíveis contratos com visitas periódicas programadas e prioridade de intervenção — contacte-nos para um orçamento personalizado.',
        'de': 'Ja, Verträge mit geplanten regelmäßigen Besuchen und vorrangigem Einsatz sind verfügbar – kontaktieren Sie uns für ein individuelles Angebot.',
    },
    'electricite.faq.2.question': {
        'en': 'Do you offer service contracts?',
        'es': '¿Ofrecen contratos de mantenimiento?',
        'it': 'Offrite contratti di manutenzione?',
        'pt': 'Oferecem contratos de manutenção?',
        'de': 'Bieten Sie Wartungsverträge an?',
    },
    'electricite.faq.3.answer': {
        'en': 'Yes, at the end of the configurator you receive a reference and can create a client area to track progress, your documents and communicate with our teams.',
        'es': 'Sí, al final del configurador recibirá una referencia y podrá crear un espacio de cliente para seguir el avance, sus documentos y comunicarse con nuestros equipos.',
        'it': "Sì, alla fine del configuratore riceverai un riferimento e potrai creare un'area cliente per seguire l'avanzamento, i tuoi documenti e comunicare con il nostro team.",
        'pt': 'Sim, no final do configurador recebe uma referência e pode criar uma área de cliente para acompanhar o progresso, os seus documentos e comunicar com as nossas equipas.',
        'de': 'Ja, am Ende des Konfigurators erhalten Sie eine Referenz und können einen Kundenbereich anlegen, um den Fortschritt und Ihre Dokumente zu verfolgen und mit unseren Teams zu kommunizieren.',
    },
    'electricite.faq.3.question': {
        'en': 'Can I track my request online?',
        'es': '¿Puedo seguir mi solicitud en línea?',
        'it': 'Posso seguire la mia richiesta online?',
        'pt': 'Posso acompanhar o meu pedido online?',
        'de': 'Kann ich meine Anfrage online verfolgen?',
    },
    'electricite.faq.4.answer': {
        'en': 'The pre-quote generated by the configurator is free and non-binding. A firm quote is issued after diagnosis or a technical visit if needed.',
        'es': 'El presupuesto generado por el configurador es gratuito y sin compromiso. Se emite un presupuesto firme tras el diagnóstico o la visita técnica si es necesario.',
        'it': 'Il preventivo generato dal configuratore è gratuito e senza impegno. Un preventivo definitivo viene emesso dopo la diagnosi o il sopralluogo tecnico se necessario.',
        'pt': 'O pré-orçamento gerado pelo configurador é gratuito e sem compromisso. É emitido um orçamento firme após diagnóstico ou visita técnica, se necessário.',
        'de': 'Das vom Konfigurator erstellte Vorabangebot ist kostenlos und unverbindlich. Ein verbindliches Angebot wird nach der Diagnose oder, falls nötig, nach einem Vor-Ort-Termin erstellt.',
    },
    'electricite.faq.4.question': {
        'en': 'Are quotes free?',
        'es': '¿Los presupuestos son gratuitos?',
        'it': 'I preventivi sono gratuiti?',
        'pt': 'Os orçamentos são gratuitos?',
        'de': 'Sind Angebote kostenlos?',
    },
    'electricite.service.alarmes.desc': {
        'en': 'Intrusion detection, alerts, remote monitoring.',
        'es': 'Detección de intrusos, alertas, teleseguimiento.',
        'it': 'Rilevamento intrusioni, allarmi, teleassistenza.',
        'pt': 'Deteção de intrusão, alertas, televigilância.',
        'de': 'Einbruchmeldung, Alarmierung, Fernüberwachung.',
    },
    'electricite.service.alarmes.name': {
        'en': 'Alarms',
        'es': 'Alarmas',
        'it': 'Allarmi',
        'pt': 'Alarmes',
        'de': 'Alarmanlagen',
    },
    'electricite.service.baies-de-brassage.desc': {
        'en': 'Installation and organisation of IT racks.',
        'es': 'Instalación y organización de racks informáticos.',
        'it': 'Installazione e organizzazione di armadi informatici.',
        'pt': 'Instalação e organização de bastidores informáticos.',
        'de': 'Einbau und Ordnung von IT-Schränken.',
    },
    'electricite.service.baies-de-brassage.name': {
        'en': 'Server racks',
        'es': 'Racks de conexión',
        'it': 'Armadi di permutazione',
        'pt': 'Bastidores de rede',
        'de': 'Netzwerkschränke',
    },
    'electricite.service.bornes-de-recharge.desc': {
        'en': 'Installation of electric vehicle charging stations.',
        'es': 'Instalación de puntos de recarga para vehículos eléctricos.',
        'it': 'Installazione di colonnine di ricarica per veicoli elettrici.',
        'pt': 'Instalação de postos de carregamento para veículos elétricos.',
        'de': 'Installation von Ladestationen für Elektrofahrzeuge.',
    },
    'electricite.service.bornes-de-recharge.name': {
        'en': 'EV charging stations',
        'es': 'Puntos de recarga',
        'it': 'Colonnine di ricarica',
        'pt': 'Postos de carregamento',
        'de': 'Ladestationen',
    },
    'electricite.service.contrats-entretien.desc': {
        'en': 'Scheduled periodic visits, priority call-out.',
        'es': 'Visitas periódicas programadas, prioridad de intervención.',
        'it': 'Visite periodiche programmate, priorità di intervento.',
        'pt': 'Visitas periódicas programadas, prioridade de intervenção.',
        'de': 'Geplante regelmäßige Besuche, vorrangiger Einsatz.',
    },
    'electricite.service.contrats-entretien.name': {
        'en': 'Service contracts',
        'es': 'Contratos de mantenimiento',
        'it': 'Contratti di manutenzione',
        'pt': 'Contratos de manutenção',
        'de': 'Wartungsverträge',
    },
    'electricite.service.controle-acces.desc': {
        'en': 'Badges, keypads, intercoms, video entry systems.',
        'es': 'Tarjetas, códigos, portero automático, videoportero.',
        'it': 'Badge, tastiere, citofoni, videocitofoni.',
        'pt': 'Cartões, códigos, intercomunicador, vídeo-porteiro.',
        'de': 'Transponder, Codetastaturen, Tür- und Videosprechanlagen.',
    },
    'electricite.service.controle-acces.name': {
        'en': 'Access control',
        'es': 'Control de acceso',
        'it': 'Controllo accessi',
        'pt': 'Controlo de acessos',
        'de': 'Zutrittskontrolle',
    },
    'electricite.service.depannage.desc': {
        'en': 'Fast response to electrical faults.',
        'es': 'Intervención rápida ante averías eléctricas.',
        'it': 'Intervento rapido su guasti elettrici.',
        'pt': 'Intervenção rápida em avarias elétricas.',
        'de': 'Schnelle Hilfe bei elektrischen Störungen.',
    },
    'electricite.service.depannage.name': {
        'en': 'Emergency repairs',
        'es': 'Reparación urgente',
        'it': 'Riparazioni urgenti',
        'pt': 'Reparação urgente',
        'de': 'Störungsdienst',
    },
    'electricite.service.domotique.desc': {
        'en': 'Centralised control of lighting, shutters, heating and scenes.',
        'es': 'Control centralizado de iluminación, persianas, calefacción y escenas.',
        'it': 'Controllo centralizzato di illuminazione, tapparelle, riscaldamento e scenari.',
        'pt': 'Controlo centralizado de iluminação, estores, aquecimento e cenas.',
        'de': 'Zentrale Steuerung von Licht, Rollläden, Heizung und Szenen.',
    },
    'electricite.service.domotique.name': {
        'en': 'Home automation',
        'es': 'Domótica',
        'it': 'Domotica',
        'pt': 'Domótica',
        'de': 'Gebäudeautomation',
    },
    'electricite.service.eclairage.desc': {
        'en': 'LED, spotlights, outdoor lighting and lighting design.',
        'es': 'LED, focos, iluminación exterior y diseño lumínico.',
        'it': 'LED, faretti, illuminazione esterna e scenografia luminosa.',
        'pt': 'LED, focos, iluminação exterior e cenarização luminosa.',
        'de': 'LED, Strahler, Außenbeleuchtung und Lichtgestaltung.',
    },
    'electricite.service.eclairage.name': {
        'en': 'Lighting',
        'es': 'Iluminación',
        'it': 'Illuminazione',
        'pt': 'Iluminação',
        'de': 'Beleuchtung',
    },
    'electricite.service.electricite-generale.desc': {
        'en': 'Installation, renovation, compliance with NF C 15-100 standards.',
        'es': 'Instalación, renovación, adaptación a la normativa NF C 15-100.',
        'it': 'Installazione, rinnovamento, messa a norma NF C 15-100.',
        'pt': 'Instalação, renovação, adequação à norma NF C 15-100.',
        'de': 'Installation, Sanierung, Anpassung an die Norm NF C 15-100.',
    },
    'electricite.service.electricite-generale.name': {
        'en': 'General electrical work',
        'es': 'Electricidad general',
        'it': 'Impianti elettrici generali',
        'pt': 'Eletricidade geral',
        'de': 'Elektroinstallation',
    },
    'electricite.service.maintenance.desc': {
        'en': 'Preventive and corrective monitoring of your installations.',
        'es': 'Seguimiento preventivo y correctivo de sus instalaciones.',
        'it': 'Monitoraggio preventivo e correttivo dei vostri impianti.',
        'pt': 'Acompanhamento preventivo e corretivo das suas instalações.',
        'de': 'Vorbeugende und korrektive Betreuung Ihrer Anlagen.',
    },
    'electricite.service.maintenance.name': {
        'en': 'Maintenance',
        'es': 'Mantenimiento',
        'it': 'Manutenzione',
        'pt': 'Manutenção',
        'de': 'Instandhaltung',
    },
    'electricite.service.reseau-informatique.desc': {
        'en': 'RJ45 cabling, patch panels, professional network infrastructure.',
        'es': 'Cableado RJ45, paneles de conexión, infraestructura de red profesional.',
        'it': 'Cablaggio RJ45, permutatori, infrastruttura di rete professionale.',
        'pt': 'Cablagem RJ45, bastidores, infraestrutura de rede profissional.',
        'de': 'RJ45-Verkabelung, Patchfelder, professionelle Netzinfrastruktur.',
    },
    'electricite.service.reseau-informatique.name': {
        'en': 'Computer networking',
        'es': 'Red informática',
        'it': 'Rete informatica',
        'pt': 'Rede informática',
        'de': 'Netzwerktechnik',
    },
    'electricite.service.videosurveillance.desc': {
        'en': 'IP cameras, recording, remote monitoring.',
        'es': 'Cámaras IP, grabación, supervisión remota.',
        'it': 'Telecamere IP, registrazione, supervisione remota.',
        'pt': 'Câmaras IP, gravação, supervisão remota.',
        'de': 'IP-Kameras, Aufzeichnung, Fernüberwachung.',
    },
    'electricite.service.videosurveillance.name': {
        'en': 'Video surveillance',
        'es': 'Videovigilancia',
        'it': 'Videosorveglianza',
        'pt': 'Videovigilância',
        'de': 'Videoüberwachung',
    },
    'electricite.service.wifi-professionnel.desc': {
        'en': 'Optimised Wi-Fi coverage for business premises.',
        'es': 'Cobertura Wi-Fi optimizada para locales profesionales.',
        'it': 'Copertura Wi-Fi ottimizzata per locali professionali.',
        'pt': 'Cobertura Wi-Fi otimizada para instalações profissionais.',
        'de': 'Optimierte WLAN-Abdeckung für Geschäftsräume.',
    },
    'electricite.service.wifi-professionnel.name': {
        'en': 'Business Wi-Fi',
        'es': 'Wi-Fi profesional',
        'it': 'Wi-Fi professionale',
        'pt': 'Wi-Fi profissional',
        'de': 'Professionelles WLAN',
    },
}
