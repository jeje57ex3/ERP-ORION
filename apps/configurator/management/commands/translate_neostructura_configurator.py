"""
manage.py translate_neostructura_configurator

Traduit en EN/DE/PT le contenu dynamique déjà seedé par
`seed_neostructura_configurator` (domaines, prestations, questions,
options, message de sécurité, mots-clés de danger) — demande utilisateur
du 2026-09-12 : « traduit aussi le configurateur » (le système de
traduction FR/EN/DE/PT déjà en place ne couvrait jusque-là que le
"chrome" statique du site React, pas ce contenu venant d'Orion).

Idempotent (update_or_create sur (objet, langue)). Le français n'a pas de
ligne de traduction : il reste porté par les champs du modèle de base,
déjà peuplés par seed_neostructura_configurator.

À exécuter après seed_neostructura_configurator (les objets de base
doivent déjà exister).
"""
from django.core.management.base import BaseCommand, CommandError

LANGS = ('en', 'de', 'pt')

# ─── Domaines ──────────────────────────────────────────────────────────────────
DOMAINS = {
    'electricite': {
        'en': {'name': 'Electrical', 'description': 'Repairs, installation, renovation, compliance upgrades, new construction.'},
        'de': {'name': 'Elektrik', 'description': 'Reparatur, Installation, Renovierung, Normkonformität, Neubau.'},
        'pt': {'name': 'Eletricidade', 'description': 'Reparação, instalação, renovação, conformidade normativa, obra nova.'},
    },
    'informatique-reseaux': {
        'en': {'name': 'IT & Networks', 'description': 'Wi-Fi, RJ45, cabling, server rack, network repair.'},
        'de': {'name': 'IT & Netzwerke', 'description': 'WLAN, RJ45, Verkabelung, Serverschrank, Netzwerkreparatur.'},
        'pt': {'name': 'Informática & Redes', 'description': 'Wi-Fi, RJ45, cablagem, bastidor informático, reparação de rede.'},
    },
    'btp-renovation': {
        'en': {'name': 'Construction / Renovation & other services', 'description': 'Renovation, waterproofing, home automation, maintenance.'},
        'de': {'name': 'Bauwesen / Renovierung & weitere Leistungen', 'description': 'Renovierung, Abdichtung, Hausautomation, Wartung.'},
        'pt': {'name': 'Construção / Renovação & outros serviços', 'description': 'Renovação, impermeabilização, domótica, manutenção.'},
    },
}

# ─── Prestations : {service_code: {lang: {'name': ...}}} ───────────────────────
SERVICES = {
    'depannage-disjoncteur': {
        'en': {'name': 'Circuit breaker keeps tripping'}, 'de': {'name': 'Sicherung löst ständig aus'}, 'pt': {'name': 'Disjuntor que dispara'},
    },
    'depannage-differentiel': {
        'en': {'name': 'RCD / residual current device keeps tripping'}, 'de': {'name': 'FI-Schutzschalter löst ständig aus'}, 'pt': {'name': 'Diferencial que dispara'},
    },
    'depannage-panne-generale': {
        'en': {'name': 'Total power outage'}, 'de': {'name': 'Kompletter Stromausfall'}, 'pt': {'name': 'Falta total de eletricidade'},
    },
    'depannage-prise': {
        'en': {'name': 'Outlet or switch no longer working'}, 'de': {'name': 'Steckdose oder Schalter funktioniert nicht mehr'}, 'pt': {'name': 'Tomada ou interruptor deixou de funcionar'},
    },
    'depannage-eclairage': {
        'en': {'name': 'Lighting not working'}, 'de': {'name': 'Beleuchtung defekt'}, 'pt': {'name': 'Iluminação avariada'},
    },
    'pose-prises': {
        'en': {'name': 'Installing outlets / switches'}, 'de': {'name': 'Installation von Steckdosen / Schaltern'}, 'pt': {'name': 'Instalação de tomadas / interruptores'},
    },
    'pose-eclairage': {
        'en': {'name': 'Installing light points'}, 'de': {'name': 'Installation von Leuchtpunkten'}, 'pt': {'name': 'Instalação de pontos de luz'},
    },
    'pose-tableau': {
        'en': {'name': 'Electrical panel replacement'}, 'de': {'name': 'Austausch des Sicherungskastens'}, 'pt': {'name': 'Substituição do quadro elétrico'},
    },
    'renovation-electrique': {
        'en': {'name': 'Electrical renovation'}, 'de': {'name': 'Elektrosanierung'}, 'pt': {'name': 'Renovação elétrica'},
    },
    'mise-normes': {
        'en': {'name': 'NF C 15-100 compliance upgrade'}, 'de': {'name': 'Normkonformität nach NF C 15-100'}, 'pt': {'name': 'Conformidade normativa NF C 15-100'},
    },
    'installation-neuve': {
        'en': {'name': 'New electrical installation (new build)'}, 'de': {'name': 'Neue Elektroinstallation (Neubau)'}, 'pt': {'name': 'Instalação elétrica nova (construção)'},
    },
    'wifi-faible': {
        'en': {'name': 'Weak Wi-Fi or dead zones'}, 'de': {'name': 'Schwaches WLAN oder Funklöcher'}, 'pt': {'name': 'Wi-Fi fraco ou zonas mortas'},
    },
    'rj45-creation': {
        'en': {'name': 'Creating RJ45 network outlets'}, 'de': {'name': 'Einrichtung von RJ45-Netzwerkdosen'}, 'pt': {'name': 'Criação de tomadas RJ45'},
    },
    'baie-informatique': {
        'en': {'name': 'Server rack / network cabinet'}, 'de': {'name': 'Serverschrank / Netzwerkschrank'}, 'pt': {'name': 'Bastidor informático / armário de rede'},
    },
    'depannage-reseau': {
        'en': {'name': 'Network troubleshooting (switch, router, cabling)'}, 'de': {'name': 'Netzwerkfehlerbehebung (Switch, Router, Verkabelung)'}, 'pt': {'name': 'Reparação de rede (switch, router, cablagem)'},
    },
    'reno-multi-corps': {
        'en': {'name': 'Multi-trade renovation'}, 'de': {'name': 'Renovierung mit mehreren Gewerken'}, 'pt': {'name': 'Renovação multi-especialidades'},
    },
    'reno-sdb': {
        'en': {'name': 'Bathroom renovation'}, 'de': {'name': 'Badezimmerrenovierung'}, 'pt': {'name': 'Renovação de casa de banho'},
    },
    'reno-cuisine': {
        'en': {'name': 'Kitchen renovation'}, 'de': {'name': 'Küchenrenovierung'}, 'pt': {'name': 'Renovação de cozinha'},
    },
    'etancheite-toiture': {
        'en': {'name': 'Flat roof waterproofing'}, 'de': {'name': 'Flachdachabdichtung'}, 'pt': {'name': 'Impermeabilização de cobertura plana'},
    },
    'etancheite-fuite': {
        'en': {'name': 'Spot leak repair'}, 'de': {'name': 'Punktuelle Leckreparatur'}, 'pt': {'name': 'Reparação pontual de fuga'},
    },
    'domotique-module': {
        'en': {'name': 'Home automation module (lighting/shutters/heating)'}, 'de': {'name': 'Hausautomationsmodul (Beleuchtung/Rollläden/Heizung)'}, 'pt': {'name': 'Módulo de domótica (iluminação/estores/aquecimento)'},
    },
    'domotique-securite': {
        'en': {'name': 'Connected security (alarm/camera)'}, 'de': {'name': 'Vernetzte Sicherheit (Alarm/Kamera)'}, 'pt': {'name': 'Segurança conectada (alarme/câmara)'},
    },
    'maintenance-contrat': {
        'en': {'name': 'Annual maintenance contract'}, 'de': {'name': 'Jährlicher Wartungsvertrag'}, 'pt': {'name': 'Contrato de manutenção anual'},
    },
    'maintenance-ponctuelle': {
        'en': {'name': 'One-off intervention (no contract)'}, 'de': {'name': 'Einmaliger Einsatz ohne Vertrag'}, 'pt': {'name': 'Intervenção pontual sem contrato'},
    },
}

# ─── Questions : {(service_code, question_id): {lang: {'label': ...}}} ─────────
# Quelques identifiants de question (type_batiment/type_logement, gamme,
# nb_points, surface...) sont réutilisés tels quels par plusieurs
# prestations avec le même libellé français — on ne les redéfinit qu'une
# fois par (service, question) puisque la table de traduction est propre à
# chaque ConfiguratorQuestion (une ligne par question, pas par identifiant).
QUESTIONS = {
    ('depannage-disjoncteur', 'moment'): {
        'en': {'label': 'Does the breaker trip immediately or after a while?'},
        'de': {'label': 'Löst die Sicherung sofort oder erst nach einer Weile aus?'},
        'pt': {'label': 'O disjuntor dispara imediatamente ou após um momento?'},
    },
    ('depannage-disjoncteur', 'danger_signes'): {
        'en': {'label': 'Smoke, sparks or a burning smell?'},
        'de': {'label': 'Rauch, Funken oder Brandgeruch?'},
        'pt': {'label': 'Fumo, faíscas ou cheiro a queimado?'},
    },
    ('depannage-disjoncteur', 'depuis_quand'): {
        'en': {'label': 'Since when has this been happening?'},
        'de': {'label': 'Seit wann tritt dieses Problem auf?'},
        'pt': {'label': 'Desde quando ocorre este problema?'},
    },
    ('depannage-disjoncteur', 'photo_tableau'): {
        'en': {'label': 'Photo of the electrical panel (optional)'},
        'de': {'label': 'Foto des Sicherungskastens (optional)'},
        'pt': {'label': 'Foto do quadro elétrico (opcional)'},
    },
    ('depannage-differentiel', 'declenche_quand'): {
        'en': {'label': 'Does the RCD trip constantly or intermittently?'},
        'de': {'label': 'Löst der FI-Schutzschalter dauerhaft oder zeitweise aus?'},
        'pt': {'label': 'O diferencial dispara permanentemente ou por intermitência?'},
    },
    ('depannage-differentiel', 'humidite'): {
        'en': {'label': 'Is the tripping related to moisture (bathroom, outdoors, rain)?'},
        'de': {'label': 'Steht das Auslösen im Zusammenhang mit Feuchtigkeit (Badezimmer, im Freien, Regen)?'},
        'pt': {'label': 'O disparo está relacionado com humidade (casa de banho, exterior, chuva)?'},
    },
    ('depannage-differentiel', 'photo_tableau'): {
        'en': {'label': 'Photo of the electrical panel (optional)'},
        'de': {'label': 'Foto des Sicherungskastens (optional)'},
        'pt': {'label': 'Foto do quadro elétrico (opcional)'},
    },
    ('depannage-panne-generale', 'voisinage'): {
        'en': {'label': 'Are your neighbours affected too?'},
        'de': {'label': 'Sind Ihre Nachbarn ebenfalls betroffen?'},
        'pt': {'label': 'Os seus vizinhos também são afetados?'},
    },
    ('depannage-panne-generale', 'depuis_quand'): {
        'en': {'label': 'Since when?'}, 'de': {'label': 'Seit wann?'}, 'pt': {'label': 'Desde quando?'},
    },
    ('depannage-prise', 'nb_points'): {
        'en': {'label': 'How many outlets/switches are affected?'},
        'de': {'label': 'Wie viele Steckdosen/Schalter sind betroffen?'},
        'pt': {'label': 'Quantas tomadas/interruptores estão em causa?'},
    },
    ('depannage-eclairage', 'nb_points'): {
        'en': {'label': 'How many light points are affected?'},
        'de': {'label': 'Wie viele Leuchtpunkte sind betroffen?'},
        'pt': {'label': 'Quantos pontos de luz estão em causa?'},
    },
    ('pose-prises', 'nb_points'): {
        'en': {'label': 'How many outlets/switches would you like installed?'},
        'de': {'label': 'Wie viele Steckdosen/Schalter möchten Sie installieren lassen?'},
        'pt': {'label': 'Quantas tomadas/interruptores deseja instalar?'},
    },
    ('pose-prises', 'gamme'): {
        'en': {'label': 'Which range would you like?'}, 'de': {'label': 'Welche Produktreihe wünschen Sie?'}, 'pt': {'label': 'Que gama deseja?'},
    },
    ('pose-eclairage', 'nb_points'): {
        'en': {'label': 'How many light points would you like installed?'},
        'de': {'label': 'Wie viele Leuchtpunkte möchten Sie installieren lassen?'},
        'pt': {'label': 'Quantos pontos de luz deseja instalar?'},
    },
    ('pose-tableau', 'age_tableau'): {
        'en': {'label': 'Is the current panel more than 20 years old?'},
        'de': {'label': 'Ist der aktuelle Sicherungskasten älter als 20 Jahre?'},
        'pt': {'label': 'O quadro atual tem mais de 20 anos?'},
    },
    ('renovation-electrique', 'surface'): {
        'en': {'label': 'Approximate area to renovate (m²)'},
        'de': {'label': 'Ungefähre zu renovierende Fläche (m²)'},
        'pt': {'label': 'Área aproximada a renovar (m²)'},
    },
    ('renovation-electrique', 'nb_pieces'): {
        'en': {'label': 'Number of rooms concerned'}, 'de': {'label': 'Anzahl der betroffenen Räume'}, 'pt': {'label': 'Número de divisões em causa'},
    },
    ('renovation-electrique', 'etat'): {
        'en': {'label': 'Current condition of the installation'},
        'de': {'label': 'Aktueller Zustand der Installation'},
        'pt': {'label': 'Estado atual da instalação'},
    },
    ('mise-normes', 'contexte'): {
        'en': {'label': 'In what context?'}, 'de': {'label': 'In welchem Rahmen?'}, 'pt': {'label': 'Em que contexto?'},
    },
    ('installation-neuve', 'type_batiment'): {
        'en': {'label': 'Building type'}, 'de': {'label': 'Gebäudetyp'}, 'pt': {'label': 'Tipo de edifício'},
    },
    ('installation-neuve', 'surface'): {
        'en': {'label': 'Area (m²)'}, 'de': {'label': 'Fläche (m²)'}, 'pt': {'label': 'Área (m²)'},
    },
    ('installation-neuve', 'gamme'): {
        'en': {'label': "Desired equipment level"}, 'de': {'label': 'Gewünschtes Ausstattungsniveau'}, 'pt': {'label': 'Nível de equipamento desejado'},
    },
    ('wifi-faible', 'type_logement'): {
        'en': {'label': 'Type of home'}, 'de': {'label': 'Wohnungstyp'}, 'pt': {'label': 'Tipo de habitação'},
    },
    ('wifi-faible', 'surface'): {
        'en': {'label': 'Approximate area (m²)'}, 'de': {'label': 'Ungefähre Fläche (m²)'}, 'pt': {'label': 'Área aproximada (m²)'},
    },
    ('wifi-faible', 'nb_etages'): {
        'en': {'label': 'Number of floors'}, 'de': {'label': 'Anzahl der Stockwerke'}, 'pt': {'label': 'Número de pisos'},
    },
    ('wifi-faible', 'nb_pieces'): {
        'en': {'label': 'Number of rooms'}, 'de': {'label': 'Anzahl der Räume'}, 'pt': {'label': 'Número de divisões'},
    },
    ('wifi-faible', 'emplacement_box'): {
        'en': {'label': 'Where is the router currently located?'},
        'de': {'label': 'Wo befindet sich der Router derzeit?'},
        'pt': {'label': 'Onde se encontra atualmente o router?'},
    },
    ('wifi-faible', 'zone_probleme'): {
        'en': {'label': 'Does the problem affect the whole home or only certain areas?'},
        'de': {'label': 'Betrifft das Problem die ganze Wohnung oder nur bestimmte Bereiche?'},
        'pt': {'label': 'O problema afeta toda a habitação ou apenas certas zonas?'},
    },
    ('wifi-faible', 'nb_zones_mortes'): {
        'en': {'label': 'How many areas are affected?'}, 'de': {'label': 'Wie viele Bereiche sind betroffen?'}, 'pt': {'label': 'Quantas zonas estão em causa?'},
    },
    ('wifi-faible', 'debit_constate'): {
        'en': {'label': 'Observed speed if known (optional)'},
        'de': {'label': 'Festgestellte Geschwindigkeit, falls bekannt (optional)'},
        'pt': {'label': 'Velocidade constatada, se souber (opcional)'},
    },
    ('wifi-faible', 'nb_appareils'): {
        'en': {'label': 'Approximate number of connected devices'},
        'de': {'label': 'Ungefähre Anzahl verbundener Geräte'},
        'pt': {'label': 'Número aproximado de dispositivos ligados'},
    },
    ('wifi-faible', 'photo_box'): {
        'en': {'label': 'Photo of the router / home (optional)'},
        'de': {'label': 'Foto des Routers / der Wohnung (optional)'},
        'pt': {'label': 'Foto do router / da habitação (opcional)'},
    },
    ('rj45-creation', 'nb_prises'): {
        'en': {'label': 'How many RJ45 outlets would you like?'},
        'de': {'label': 'Wie viele RJ45-Dosen wünschen Sie?'},
        'pt': {'label': 'Quantas tomadas RJ45 deseja?'},
    },
    ('rj45-creation', 'type_batiment'): {
        'en': {'label': 'Building type'}, 'de': {'label': 'Gebäudetyp'}, 'pt': {'label': 'Tipo de edifício'},
    },
    ('rj45-creation', 'distance'): {
        'en': {'label': 'Approximate distance between the rack and the furthest point'},
        'de': {'label': 'Ungefähre Entfernung zwischen Verteilerschrank und dem am weitesten entfernten Punkt'},
        'pt': {'label': 'Distância aproximada entre o bastidor e o ponto mais distante'},
    },
    ('rj45-creation', 'cablage_existant'): {
        'en': {'label': 'Is there existing network cabling?'},
        'de': {'label': 'Ist bereits eine Netzwerkverkabelung vorhanden?'},
        'pt': {'label': 'Já existe cablagem de rede?'},
    },
    ('rj45-creation', 'contexte'): {
        'en': {'label': 'Renovation or new construction?'}, 'de': {'label': 'Renovierung oder Neubau?'}, 'pt': {'label': 'Renovação ou construção nova?'},
    },
    ('baie-informatique', 'nb_equipements'): {
        'en': {'label': 'Approximate number of devices to install (switch, router...)'},
        'de': {'label': 'Ungefähre Anzahl der zu installierenden Geräte (Switch, Router...)'},
        'pt': {'label': 'Número aproximado de equipamentos a instalar (switch, router...)'},
    },
    ('depannage-reseau', 'symptome'): {
        'en': {'label': 'What are you experiencing?'}, 'de': {'label': 'Was stellen Sie fest?'}, 'pt': {'label': 'O que constata?'},
    },
    ('depannage-reseau', 'equipements_concernes'): {
        'en': {'label': 'Which devices are affected?'}, 'de': {'label': 'Welche Geräte sind betroffen?'}, 'pt': {'label': 'Que equipamentos estão em causa?'},
    },
    ('reno-multi-corps', 'surface'): {
        'en': {'label': 'Area to renovate (m²)'}, 'de': {'label': 'Zu renovierende Fläche (m²)'}, 'pt': {'label': 'Área a renovar (m²)'},
    },
    ('etancheite-toiture', 'surface'): {
        'en': {'label': 'Roof area (m²)'}, 'de': {'label': 'Dachfläche (m²)'}, 'pt': {'label': 'Área de cobertura (m²)'},
    },
    ('etancheite-fuite', 'localisation'): {
        'en': {'label': 'Where is the leak located?'}, 'de': {'label': 'Wo befindet sich das festgestellte Leck?'}, 'pt': {'label': 'Onde se localiza a fuga constatada?'},
    },
    ('domotique-module', 'nb_modules'): {
        'en': {'label': 'How many modules would you like?'}, 'de': {'label': 'Wie viele Module wünschen Sie?'}, 'pt': {'label': 'Quantos módulos deseja?'},
    },
    ('domotique-securite', 'nb_points'): {
        'en': {'label': 'How many security points?'}, 'de': {'label': 'Wie viele Sicherheitspunkte?'}, 'pt': {'label': 'Quantos pontos de segurança?'},
    },
}

# ─── Options : {(service_code, question_id, value): {lang: label}} ────────────
OPTIONS = {
    ('depannage-disjoncteur', 'moment', 'immediat'): {'en': 'Immediately', 'de': 'Sofort', 'pt': 'Imediatamente'},
    ('depannage-disjoncteur', 'moment', 'apres_moment'): {'en': 'After a while', 'de': 'Nach einer Weile', 'pt': 'Após um momento'},
    ('depannage-disjoncteur', 'moment', 'aleatoire'): {'en': 'Randomly', 'de': 'Zufällig', 'pt': 'De forma aleatória'},

    ('depannage-differentiel', 'declenche_quand', 'permanent'): {'en': 'Constantly', 'de': 'Dauerhaft', 'pt': 'Permanentemente'},
    ('depannage-differentiel', 'declenche_quand', 'intermittent'): {'en': 'Intermittently', 'de': 'Zeitweise', 'pt': 'Por intermitência'},
    ('depannage-differentiel', 'declenche_quand', 'appareil_precis'): {'en': 'When I use a specific appliance', 'de': 'Bei Nutzung eines bestimmten Geräts', 'pt': 'Quando uso um aparelho específico'},

    ('pose-prises', 'gamme', 'standard'): {'en': 'Standard', 'de': 'Standard', 'pt': 'Standard'},
    ('pose-prises', 'gamme', 'premium'): {'en': 'Premium', 'de': 'Premium', 'pt': 'Premium'},
    ('pose-prises', 'gamme', 'luxe'): {'en': 'Luxury', 'de': 'Luxus', 'pt': 'Luxo'},

    ('renovation-electrique', 'etat', 'bon'): {'en': 'Good', 'de': 'Gut', 'pt': 'Bom'},
    ('renovation-electrique', 'etat', 'moyen'): {'en': 'Average', 'de': 'Mittel', 'pt': 'Médio'},
    ('renovation-electrique', 'etat', 'vetuste'): {'en': 'Outdated', 'de': 'Veraltet', 'pt': 'Antiquado'},
    ('renovation-electrique', 'etat', 'inconnu'): {'en': "I don't know", 'de': 'Ich weiß es nicht', 'pt': 'Não sei'},

    ('mise-normes', 'contexte', 'vente'): {'en': 'Property sale', 'de': 'Immobilienverkauf', 'pt': 'Venda do imóvel'},
    ('mise-normes', 'contexte', 'diagnostic_defavorable'): {'en': 'Following an unfavourable diagnosis', 'de': 'Nach ungünstiger Diagnose', 'pt': 'Na sequência de um diagnóstico desfavorável'},
    ('mise-normes', 'contexte', 'securite'): {'en': 'Voluntary safety upgrade', 'de': 'Freiwillige Sicherheitsverbesserung', 'pt': 'Melhoria de segurança voluntária'},

    ('installation-neuve', 'type_batiment', 'maison'): {'en': 'House', 'de': 'Haus', 'pt': 'Casa'},
    ('installation-neuve', 'type_batiment', 'appartement'): {'en': 'Apartment', 'de': 'Wohnung', 'pt': 'Apartamento'},
    ('installation-neuve', 'type_batiment', 'local_pro'): {'en': 'Commercial premises', 'de': 'Gewerberäume', 'pt': 'Instalações comerciais'},
    ('installation-neuve', 'gamme', 'standard'): {'en': 'Standard', 'de': 'Standard', 'pt': 'Standard'},
    ('installation-neuve', 'gamme', 'premium'): {'en': 'Premium', 'de': 'Premium', 'pt': 'Premium'},
    ('installation-neuve', 'gamme', 'luxe'): {'en': 'Luxury', 'de': 'Luxus', 'pt': 'Luxo'},

    ('wifi-faible', 'type_logement', 'maison'): {'en': 'House', 'de': 'Haus', 'pt': 'Casa'},
    ('wifi-faible', 'type_logement', 'appartement'): {'en': 'Apartment', 'de': 'Wohnung', 'pt': 'Apartamento'},
    ('wifi-faible', 'type_logement', 'local_pro'): {'en': 'Commercial premises', 'de': 'Gewerberäume', 'pt': 'Instalações comerciais'},
    ('wifi-faible', 'emplacement_box', 'rdc'): {'en': 'Ground floor', 'de': 'Erdgeschoss', 'pt': 'Rés-do-chão'},
    ('wifi-faible', 'emplacement_box', 'etage'): {'en': 'Upper floor', 'de': 'Obergeschoss', 'pt': 'Andar'},
    ('wifi-faible', 'emplacement_box', 'sous_sol'): {'en': 'Basement / technical room', 'de': 'Keller / Technikraum', 'pt': 'Cave / sala técnica'},
    ('wifi-faible', 'zone_probleme', 'partout'): {'en': 'Everywhere', 'de': 'Überall', 'pt': 'Em toda a parte'},
    ('wifi-faible', 'zone_probleme', 'certaines_zones'): {'en': 'Only certain areas', 'de': 'Nur bestimmte Bereiche', 'pt': 'Apenas certas zonas'},

    ('rj45-creation', 'type_batiment', 'maison'): {'en': 'House', 'de': 'Haus', 'pt': 'Casa'},
    ('rj45-creation', 'type_batiment', 'appartement'): {'en': 'Apartment', 'de': 'Wohnung', 'pt': 'Apartamento'},
    ('rj45-creation', 'type_batiment', 'local_pro'): {'en': 'Commercial premises', 'de': 'Gewerberäume', 'pt': 'Instalações comerciais'},
    ('rj45-creation', 'contexte', 'renovation'): {'en': 'Renovation', 'de': 'Renovierung', 'pt': 'Renovação'},
    ('rj45-creation', 'contexte', 'neuf'): {'en': 'New build', 'de': 'Neubau', 'pt': 'Novo'},

    ('depannage-reseau', 'symptome', 'aucune_connexion'): {'en': 'No connection', 'de': 'Keine Verbindung', 'pt': 'Sem ligação'},
    ('depannage-reseau', 'symptome', 'connexion_intermittente'): {'en': 'Intermittent connection', 'de': 'Zeitweise Verbindung', 'pt': 'Ligação intermitente'},
    ('depannage-reseau', 'symptome', 'lenteur'): {'en': 'Significant slowness', 'de': 'Deutliche Verlangsamung', 'pt': 'Lentidão significativa'},
    ('depannage-reseau', 'symptome', 'poste_isole'): {'en': 'Only one device is affected', 'de': 'Nur ein Gerät betroffen', 'pt': 'Apenas um posto deixou de funcionar'},
    ('depannage-reseau', 'equipements_concernes', 'switch'): {'en': 'Switch', 'de': 'Switch', 'pt': 'Switch'},
    ('depannage-reseau', 'equipements_concernes', 'routeur'): {'en': 'Router', 'de': 'Router', 'pt': 'Router'},
    ('depannage-reseau', 'equipements_concernes', 'cablage'): {'en': 'Cabling', 'de': 'Verkabelung', 'pt': 'Cablagem'},
    ('depannage-reseau', 'equipements_concernes', 'baie'): {'en': 'Server rack', 'de': 'Serverschrank', 'pt': 'Bastidor informático'},
}

# ─── Diagnostic : message de sécurité + mots-clés (traduits pour que la
# détection de danger fonctionne sur du texte libre écrit dans une langue
# non française — §16-17). Même message de sécurité générique que le
# modèle de base (repris tel quel pour les 3 scénarios électriques qui
# peuvent réellement déclencher une alerte danger). ────────────────────────────
SAFETY_MESSAGE = {
    'en': "This may involve an electrical hazard. If possible, switch off the relevant breaker and contact us "
          "immediately — do not attempt to fix it yourself.",
    'de': "Hierbei könnte es sich um eine elektrische Gefahr handeln. Schalten Sie nach Möglichkeit die "
          "betreffende Sicherung aus und kontaktieren Sie uns sofort — greifen Sie nicht selbst ein.",
    'pt': "Isto pode envolver um risco elétrico. Se possível, desligue o disjuntor em causa e contacte-nos "
          "imediatamente — não intervenha por si próprio.",
}

DIAGNOSTIC_SCENARIOS = {
    'depannage-disjoncteur': {
        'en': ['smoke', 'spark', 'burnt', 'burning', 'hot', 'heat'],
        'de': ['rauch', 'funke', 'verbrannt', 'brand', 'heiß', 'hitze'],
        'pt': ['fumo', 'faísca', 'queimado', 'quente', 'calor'],
    },
    'depannage-differentiel': {
        'en': ['smoke', 'spark', 'burnt', 'electric shock'],
        'de': ['rauch', 'funke', 'verbrannt', 'stromschlag'],
        'pt': ['fumo', 'faísca', 'queimado', 'choque elétrico'],
    },
    'depannage-panne-generale': {
        'en': ['smoke', 'spark', 'burnt', 'smell'],
        'de': ['rauch', 'funke', 'verbrannt', 'geruch'],
        'pt': ['fumo', 'faísca', 'queimado', 'cheiro'],
    },
    # Ces trois scénarios existent (requires_diagnostic=True) mais n'ont pas
    # de mots-clés de danger dans le seed d'origine — le message de sécurité
    # générique est tout de même traduit par cohérence si danger_alert /
    # des mots-clés y sont ajoutés plus tard depuis l'admin.
    'wifi-faible': {'en': [], 'de': [], 'pt': []},
    'depannage-reseau': {'en': [], 'de': [], 'pt': []},
    'etancheite-fuite': {'en': [], 'de': [], 'pt': []},
}


class Command(BaseCommand):
    help = 'Traduit en EN/DE/PT le contenu du configurateur NÉOSTRUCTURA (après seed_neostructura_configurator).'

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.configurator.models import (
            ServiceDomain, ServiceCategory, ConfiguratorQuestion, ConfiguratorQuestionOption,
            DiagnosticScenario, ServiceDomainTranslation, ServiceCategoryTranslation,
            ConfiguratorQuestionTranslation, ConfiguratorQuestionOptionTranslation,
            DiagnosticScenarioTranslation,
        )

        try:
            company = Company.objects.get(slug='neostructura')
        except Company.DoesNotExist:
            raise CommandError("Entreprise 'neostructura' introuvable.")

        n_domains = n_services = n_questions = n_options = n_scenarios = 0

        for code, langs in DOMAINS.items():
            domain = ServiceDomain.objects.filter(company=company, code=code).first()
            if not domain:
                self.stdout.write(self.style.WARNING(f'Domaine introuvable : {code} (ignoré)'))
                continue
            for lang, fields in langs.items():
                ServiceDomainTranslation.objects.update_or_create(domain=domain, language=lang, defaults=fields)
                n_domains += 1

        for code, langs in SERVICES.items():
            service = ServiceCategory.objects.filter(domain__company=company, code=code).first()
            if not service:
                self.stdout.write(self.style.WARNING(f'Prestation introuvable : {code} (ignorée)'))
                continue
            for lang, fields in langs.items():
                ServiceCategoryTranslation.objects.update_or_create(service=service, language=lang, defaults=fields)
                n_services += 1

        for (service_code, question_id), langs in QUESTIONS.items():
            question = ConfiguratorQuestion.objects.filter(
                service__domain__company=company, service__code=service_code, identifier=question_id,
            ).first()
            if not question:
                self.stdout.write(self.style.WARNING(f'Question introuvable : {service_code}/{question_id} (ignorée)'))
                continue
            for lang, fields in langs.items():
                ConfiguratorQuestionTranslation.objects.update_or_create(question=question, language=lang, defaults=fields)
                n_questions += 1

        for (service_code, question_id, value), langs in OPTIONS.items():
            option = ConfiguratorQuestionOption.objects.filter(
                question__service__domain__company=company, question__service__code=service_code,
                question__identifier=question_id, value=value,
            ).first()
            if not option:
                self.stdout.write(self.style.WARNING(f'Option introuvable : {service_code}/{question_id}={value} (ignorée)'))
                continue
            for lang, label in langs.items():
                ConfiguratorQuestionOptionTranslation.objects.update_or_create(
                    option=option, language=lang, defaults={'label': label},
                )
                n_options += 1

        for service_code, keywords_by_lang in DIAGNOSTIC_SCENARIOS.items():
            scenario = DiagnosticScenario.objects.filter(
                service__domain__company=company, service__code=service_code,
            ).first()
            if not scenario:
                self.stdout.write(self.style.WARNING(f'Scénario de diagnostic introuvable : {service_code} (ignoré)'))
                continue
            for lang in LANGS:
                DiagnosticScenarioTranslation.objects.update_or_create(
                    scenario=scenario, language=lang,
                    defaults={
                        'safety_message': SAFETY_MESSAGE[lang],
                        'danger_keywords': keywords_by_lang.get(lang, []),
                    },
                )
                n_scenarios += 1

        self.stdout.write(self.style.SUCCESS(
            f'{n_domains} traduction(s) de domaine, {n_services} de prestation, {n_questions} de question, '
            f'{n_options} d\'option, {n_scenarios} de scénario de diagnostic.'
        ))
