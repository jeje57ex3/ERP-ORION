"""apps/btp/modeles_prets.py — modèles de chantier prêts à l'emploi.

Un modèle utile fait trente à quarante questions. Les retaper à la main
avant de pouvoir se servir de la fonctionnalité en condamnerait l'usage :
personne ne commence par saisir quarante lignes dans un écran vide.

Ce fichier contient donc un modèle de départ complet, installable **d'un
bouton** depuis la liste des modèles. Pas de commande à taper — c'est une
contrainte explicite du projet : tout ce qui relève de l'administration doit
être pilotable depuis l'interface.

Ce n'est qu'un POINT DE DÉPART. Une fois installé, c'est un modèle ordinaire :
on y ajoute, on en retire, on le duplique pour en faire une variante. Rien
ici n'est figé dans le code après l'installation, et c'est volontaire —
sinon la liste de questions dépendrait d'une mise à jour du logiciel.

Format de chaque point : (libellé, type, obligatoire, unité, options, aide)
"""

CATALOGUE_DES_MODELES = {
    'electricite': {
        'nom': 'Électricité — chantier complet',
        'description': (
            'De la visite technique à la réception : les étapes habituelles '
            'd\'un chantier d\'électricité, avec les points à relever sur '
            'place pour ne rien découvrir le jour de la pose.'),
        'etapes': [
            {
                'nom': 'Analyse sur place',
                'type': 'technical_visit',
                'decalage': -7,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Accès au chantier possible en camionnette ?', 'yes_no',
                     True, '', [],
                     'Largeur de passage, portail, hauteur sous porche.'),
                    ('Une nacelle est-elle nécessaire ?', 'yes_no', True, '',
                     [], 'À réserver dès la commande du matériel si oui.'),
                    ('Un échafaudage est-il nécessaire ?', 'yes_no', False,
                     '', [], ''),
                    ('Hauteur sous plafond', 'number', True, 'm', [],
                     'La plus grande hauteur de la zone de travail.'),
                    ('Nature des murs', 'choice', True, '',
                     ['Placo', 'Brique', 'Béton', 'Pierre', 'Ossature bois',
                      'Mixte'],
                     'Détermine l\'outillage et le temps de saignée.'),
                    ('État du tableau existant', 'choice', True, '',
                     ['Aux normes', 'À remplacer', 'À compléter',
                      'Pas de tableau', 'À confirmer'], ''),
                    ('Emplacement du compteur', 'text', False, '', [],
                     'Et son accessibilité : cave, placard, extérieur…'),
                    ('Photo du tableau existant', 'photo', True, '', [], ''),
                    ('Photo de l\'accès au chantier', 'photo', False, '', [],
                     'Évite la mauvaise surprise le jour de la livraison.'),
                    ('Présence d\'amiante suspectée ?', 'yes_no', True, '',
                     [], 'Bâtiment antérieur à 1997 : diagnostic à demander.'),
                    ('Électricité disponible sur place pendant les travaux ?',
                     'yes_no', True, '', [], ''),
                    ('Stationnement possible devant le chantier ?', 'yes_no',
                     False, '', [], ''),
                    ('Point d\'eau disponible ?', 'yes_no', False, '', [], ''),
                    ('Code d\'accès ou interphone', 'text', False, '', [], ''),
                    ('Personne à contacter sur place', 'text', False, '', [],
                     'Nom et téléphone.'),
                    ('Surface concernée', 'number', False, 'm²', [], ''),
                ],
            },
            {
                'nom': 'Validation du devis',
                'type': 'quote_validation',
                'decalage': -3,
                'visible_client': True,
                'client_valide': True,
                'points': [
                    ('Devis signé reçu ?', 'yes_no', True, '', [], ''),
                    ('Devis concerné', 'quote', True, '', [],
                     'Désignez la fiche du devis : son numéro, son '
                     'montant et son statut suivent tout seuls.'),
                    ('Date de signature', 'date', False, '', [], ''),
                    ('Acompte encaissé ?', 'yes_no', False, '', [], ''),
                    ('Montant de l\'acompte', 'number', False, '€', [], ''),
                ],
            },
            {
                'nom': 'Commande du matériel',
                'type': 'material_prep',
                'decalage': -2,
                'visible_client': False,
                'client_valide': False,
                'points': [
                    ('Métré validé ?', 'yes_no', True, '', [], ''),
                    ('Liste de matériel établie ?', 'yes_no', True, '', [],
                     ''),
                    ('Fournisseur retenu', 'supplier', True, '', [],
                     'La fiche fournisseur : coordonnées et délai '
                     'annoncé viennent avec.'),
                    ('Devis de référence', 'quote', False, '', [],
                     'Le devis client que cette commande sert, pour '
                     'rapprocher la dépense de ce qui a été vendu.'),
                    ('Numéro de commande ou de devis fournisseur',
                     'text', False, '', [],
                     'La référence côté fournisseur, à rappeler en cas '
                     'de litige sur la livraison.'),
                    ('Commande passée au fournisseur le', 'date', True, '',
                     [], ''),
                    ('Date de livraison annoncée', 'date', True, '', [], ''),
                    ('Lieu de livraison', 'choice', True, '',
                     ['Sur le chantier', 'Au dépôt', 'Retrait au négoce'],
                     ''),
                    ('Nacelle réservée', 'yes_no', False, '', [],
                     'À remplir si l\'analyse sur place en demandait une.'),
                    ('Échafaudage réservé', 'yes_no', False, '', [], ''),
                    ('Benne commandée', 'yes_no', False, '', [], ''),
                    ('Montant de la commande', 'number', False, '€', [], ''),
                ],
            },
            {
                'nom': 'Préparation administrative',
                'type': 'other',
                'decalage': -1,
                'visible_client': False,
                'client_valide': False,
                'points': [
                    ('Autorisation de voirie nécessaire ?', 'yes_no', False,
                     '', [], 'Stationnement de la nacelle ou de la benne.'),
                    ('PPSPS ou plan de prévention demandé ?', 'yes_no', False,
                     '', [], ''),
                    ('Attestation d\'assurance transmise au client ?',
                     'yes_no', False, '', [], ''),
                    ('Habilitations électriques des intervenants à jour ?',
                     'yes_no', True, '', [], ''),
                ],
            },
            {
                'nom': 'Début des travaux',
                'type': 'work_start',
                'decalage': 0,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Consignation réalisée ?', 'yes_no', True, '', [],
                     'Coupure, condamnation, vérification d\'absence de '
                     'tension.'),
                    ('Protection des sols et des meubles en place ?',
                     'yes_no', True, '', [], ''),
                    ('Matériel livré et contrôlé ?', 'yes_no', True, '', [],
                     ''),
                ],
            },
            {
                'nom': 'Passage des câbles',
                'type': 'cable_pass',
                'decalage': 2,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Saignées et percements terminés ?', 'yes_no', False, '',
                     [], ''),
                    ('Gaines tirées ?', 'yes_no', False, '', [], ''),
                    ('Repérage des circuits fait ?', 'yes_no', True, '', [],
                     ''),
                ],
            },
            {
                'nom': 'Pose de l\'appareillage',
                'type': 'fitting',
                'decalage': 6,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Nombre de prises posées', 'number', False, 'u', [], ''),
                    ('Nombre de points lumineux posés', 'number', False, 'u',
                     [], ''),
                    ('Appareillage conforme au devis ?', 'yes_no', True, '',
                     [], 'Référence, teinte, finition.'),
                ],
            },
            {
                'nom': 'Tableau électrique',
                'type': 'panel',
                'decalage': 8,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Tableau posé et raccordé ?', 'yes_no', True, '', [],
                     ''),
                    ('Étiquetage des circuits fait ?', 'yes_no', True, '', [],
                     ''),
                    ('Schéma du tableau remis ?', 'yes_no', False, '', [],
                     ''),
                    ('Photo du tableau terminé', 'photo', False, '', [], ''),
                ],
            },
            {
                'nom': 'Tests et mise en service',
                'type': 'tests',
                'decalage': 9,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Mesure de la prise de terre', 'number', True, 'Ω', [],
                     ''),
                    ('Continuité des conducteurs de protection vérifiée ?',
                     'yes_no', True, '', [], ''),
                    ('Différentiels testés ?', 'yes_no', True, '', [], ''),
                    ('Attestation Consuel nécessaire ?', 'yes_no', True, '',
                     [], ''),
                    ('Date d\'envoi du Consuel', 'date', False, '', [], ''),
                ],
            },
            {
                'nom': 'Nettoyage',
                'type': 'cleaning',
                'decalage': 10,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Gravats évacués ?', 'yes_no', True, '', [], ''),
                    ('Chantier nettoyé ?', 'yes_no', True, '', [], ''),
                ],
            },
            {
                'nom': 'Réception du chantier',
                'type': 'reception',
                'decalage': 11,
                'visible_client': True,
                'client_valide': True,
                'points': [
                    ('Procès-verbal de réception signé ?', 'yes_no', True, '',
                     [], ''),
                    ('Réserves émises par le client', 'text', False, '', [],
                     'À reporter ensuite dans les réserves du chantier.'),
                    ('Notice d\'utilisation remise ?', 'yes_no', False, '',
                     [], ''),
                    ('Photo du chantier terminé', 'photo', False, '', [], ''),
                ],
            },
        ],
    },
    'etancheite': {
        'nom': 'Étanchéité — toiture-terrasse',
        'description': (
            'Le métier où la surprise coûte le plus cher : ce qu\'il y a '
            'SOUS l\'ancienne étanchéité ne se voit qu\'au sondage, et se '
            'découvre sinon une fois le toit ouvert. Ce modèle force le '
            'sondage, le diagnostic amiante, la pente, les relevés et les '
            'évacuations AVANT la commande — et impose la mise en eau avant '
            'la réception.'),
        'etapes': [
            {
                'nom': 'Analyse sur place — accès et support',
                'type': 'technical_visit',
                'decalage': -21,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Comment accède-t-on au toit ?', 'choice', True, '',
                     ['Escalier intérieur', 'Trappe et échelle de meunier',
                      'Échelle extérieure', 'Nacelle', 'Échafaudage',
                      'Toit voisin'],
                     'Détermine comment monte le matériel, pas seulement '
                     'les hommes.'),
                    ('Hauteur du bâtiment', 'number', True, 'm', [],
                     'Du sol à l\'acrotère.'),
                    ('Accès camion jusqu\'au pied du bâtiment ?', 'yes_no',
                     True, '', [], ''),
                    ('Nacelle nécessaire ?', 'yes_no', True, '', [], ''),
                    ('Échafaudage nécessaire ?', 'yes_no', True, '', [], ''),
                    ('Monte-matériaux ou grue nécessaire ?', 'yes_no', True,
                     '', [],
                     'Un rouleau de bitume pèse 40 kg et il en faut un par '
                     '7 m² : la question se pose presque toujours.'),
                    ('Zone de stockage sur place possible ?', 'yes_no', True,
                     '', [], ''),
                    ('Autorisation de voirie nécessaire ?', 'yes_no', True,
                     '', [], 'Stationnement de la nacelle, de la grue ou de '
                     'la benne.'),
                    ('Surface à traiter', 'number', True, 'm²', [], ''),
                    ('Type de support', 'choice', True, '',
                     ['Béton', 'Bac acier', 'Bois / panneaux',
                      'Maçonnerie', 'Ancienne étanchéité conservée',
                      'À confirmer après sondage'], ''),
                    ('Pente du toit', 'number', True, '%', [],
                     'Une pente nulle fait stagner l\'eau : à signaler au '
                     'client avant travaux, pas après.'),
                    ('Des zones de stagnation sont-elles visibles ?',
                     'yes_no', True, '', [],
                     'Flaques, traces, mousses, dépôts.'),
                    ('Électricité disponible en toiture ?', 'yes_no', False,
                     '', [], ''),
                    ('Point d\'eau disponible ?', 'yes_no', False, '', [],
                     'Nécessaire pour la mise en eau de fin de chantier.'),
                    ('Photo de la toiture dans son ensemble', 'photo', True,
                     '', [], ''),
                    ('Photo de l\'accès au toit', 'photo', False, '', [], ''),
                    ('Personne à contacter sur place', 'text', False, '', [],
                     'Nom et téléphone.'),
                    ('Code d\'accès, clé de la trappe', 'text', False, '',
                     [], ''),
                ],
            },
            {
                'nom': 'Analyse sur place — sondage et amiante',
                'type': 'technical_visit',
                'decalage': -20,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Nature de l\'étanchéité existante', 'choice', True, '',
                     ['Bitume soudé', 'Bitume auto-protégé', 'Asphalte',
                      'EPDM', 'PVC', 'TPO', 'Résine', 'Aucune',
                      'Inconnue avant sondage'], ''),
                    ('Nombre de couches en place', 'number', True, 'u', [],
                     'Au-delà de deux, la surcharge interdit souvent de '
                     'poser par-dessus.'),
                    ('Un sondage ou carottage a-t-il été réalisé ?', 'yes_no',
                     True, '', [],
                     'C\'est LE point du métier : sans sondage, on ne sait '
                     'ni ce qu\'il y a dessous ni si c\'est sec.'),
                    ('Date du sondage', 'date', False, '', [], ''),
                    ('Photo du sondage', 'photo', True, '', [], ''),
                    ('État de l\'isolation existante', 'choice', True, '',
                     ['Sèche', 'Humide par endroits', 'Détrempée', 'Absente',
                      'Inconnu avant sondage'], ''),
                    ('Amiante suspectée dans l\'ancienne étanchéité ?',
                     'yes_no', True, '', [],
                     'Bitume ou colle antérieurs à 1997 : le diagnostic est '
                     'obligatoire avant toute dépose.'),
                    ('Diagnostic amiante fourni par le client ?', 'yes_no',
                     True, '', [], ''),
                    ('Date du diagnostic amiante', 'date', False, '', [], ''),
                    ('Résultat du diagnostic amiante', 'choice', False, '',
                     ['Négatif', 'Positif', 'En attente',
                      'Non réalisé'], ''),
                    ('Y a-t-il des infiltrations actives ?', 'yes_no', True,
                     '', [], ''),
                    ('Où se manifestent les infiltrations ?', 'text', False,
                     '', [],
                     'Pièce, plafond, mur : repérer AVANT de refermer.'),
                    ('Photo des infiltrations côté intérieur', 'photo', False,
                     '', [], ''),
                    ('Qu\'y a-t-il sous la toiture ?', 'text', True, '', [],
                     'Logement occupé, local technique, serveurs, stock : '
                     'ce qui se trouve dessous décide des protections.'),
                ],
            },
            {
                'nom': 'Analyse sur place — relevés, évacuations, sécurité',
                'type': 'technical_visit',
                'decalage': -19,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Nombre d\'évacuations d\'eau pluviale', 'number', True,
                     'u', [], ''),
                    ('État des évacuations', 'choice', True, '',
                     ['Bon', 'Encrassées', 'Bouchées', 'Sous-dimensionnées',
                      'À remplacer'], ''),
                    ('Des trop-pleins sont-ils présents ?', 'yes_no', True,
                     '', [],
                     'Leur absence est un défaut fréquent : sans eux, une '
                     'évacuation bouchée transforme le toit en piscine.'),
                    ('Nombre de relevés et acrotères', 'number', False, 'u',
                     [], ''),
                    ('Hauteur des relevés existants', 'number', True, 'cm',
                     [],
                     'Moins de 15 cm au-dessus de la protection : non '
                     'conforme, à reprendre.'),
                    ('État des acrotères', 'choice', True, '',
                     ['Bon', 'Fissurés', 'Couronnement dégradé',
                      'Bandes de solin à reprendre', 'À reconstruire'], ''),
                    ('Nombre de traversées à traiter', 'number', True, 'u',
                     [],
                     'Ventilations, antennes, câbles, fourreaux : chacune '
                     'est une fuite potentielle.'),
                    ('Y a-t-il des lanterneaux ou costières ?', 'yes_no',
                     False, '', [], ''),
                    ('Y a-t-il des équipements posés en toiture ?', 'yes_no',
                     True, '', [],
                     'Climatisation, panneaux solaires, antennes : à '
                     'déposer ou à contourner, et c\'est du temps.'),
                    ('Lesquels, et faut-il les déposer ?', 'text', False, '',
                     [], ''),
                    ('Destination de la toiture', 'choice', True, '',
                     ['Inaccessible', 'Accessible technique',
                      'Terrasse accessible', 'Parking', 'Toiture végétalisée'],
                     'Décide de la protection lourde et du complexe.'),
                    ('Garde-corps ou ligne de vie en place ?', 'yes_no', True,
                     '', [], ''),
                    ('Protection collective provisoire à prévoir ?', 'yes_no',
                     True, '', [], ''),
                    ('Végétation ou gravillons à retirer ?', 'yes_no', False,
                     '', [], ''),
                    ('Benne possible, et où ?', 'text', True, '', [],
                     'Emplacement et accès : une benne qu\'on ne peut pas '
                     'poser arrête le chantier.'),
                    ('Photo des relevés et acrotères', 'photo', True, '', [],
                     ''),
                    ('Photo des évacuations', 'photo', True, '', [], ''),
                ],
            },
            {
                'nom': 'Contraintes, sécurité et autorisations',
                'type': 'other',
                'decalage': -14,
                'visible_client': False,
                'client_valide': False,
                'points': [
                    ('Travaux par point chaud nécessaires ?', 'yes_no', True,
                     '', [],
                     'Soudure au chalumeau : permis de feu et extincteurs '
                     'obligatoires.'),
                    ('Permis de feu nécessaire ?', 'yes_no', True, '', [],
                     ''),
                    ('Permis de feu obtenu le', 'date', False, '', [], ''),
                    ('Extincteurs sur place prévus ?', 'yes_no', True, '', [],
                     ''),
                    ('Ronde de surveillance après soudure prévue ?', 'yes_no',
                     True, '', [],
                     'Deux heures après l\'arrêt du chalumeau : un feu de '
                     'toiture part en couvant.'),
                    ('Plan de prévention ou PPSPS demandé ?', 'yes_no', False,
                     '', [], ''),
                    ('Autorisation de voirie demandée le', 'date', False, '',
                     [], ''),
                    ('Déclaration préalable nécessaire ?', 'yes_no', False,
                     '', [],
                     'Changement d\'aspect, isolation par l\'extérieur.'),
                    ('Attestation d\'assurance décennale transmise ?',
                     'yes_no', True, '', [], ''),
                    ('Occupants prévenus du bruit et des odeurs ?', 'yes_no',
                     True, '', [],
                     'Le bitume chaud s\'invite dans les logements par les '
                     'ventilations.'),
                    ('Protection des locaux en dessous prévue ?', 'yes_no',
                     True, '', [], ''),
                    ('Période de travaux retenue', 'text', True, '', [],
                     'Une étanchéité ne se pose pas sous la pluie ni en '
                     'gel : la fenêtre météo fait partie du devis.'),
                ],
            },
            {
                'nom': 'Validation du devis',
                'type': 'quote_validation',
                'decalage': -10,
                'visible_client': True,
                'client_valide': True,
                'points': [
                    ('Devis signé reçu ?', 'yes_no', True, '', [], ''),
                    ('Devis concerné', 'quote', True, '', [],
                     'Désignez la fiche du devis : son numéro, son '
                     'montant et son statut suivent tout seuls.'),
                    ('Date de signature', 'date', False, '', [], ''),
                    ('Acompte encaissé ?', 'yes_no', False, '', [], ''),
                    ('Le devis couvre-t-il la dépose de l\'existant ?',
                     'yes_no', True, '', [],
                     'La dépose est le poste le plus souvent oublié, et le '
                     'plus lourd.'),
                    ('Le devis couvre-t-il le traitement de l\'amiante ?',
                     'yes_no', True, '', [],
                     'Si le diagnostic est positif. Sinon, répondre non et '
                     'le dire au client AVANT de monter.'),
                    ('Le devis couvre-t-il la reprise des évacuations ?',
                     'yes_no', True, '', [], ''),
                    ('Le devis couvre-t-il les relevés et acrotères ?',
                     'yes_no', True, '', [], ''),
                    ('Le devis couvre-t-il la reprise du support ?', 'yes_no',
                     True, '', [],
                     'Ce que le sondage a révélé : forme de pente, béton '
                     'dégradé, bac acier percé.'),
                    ('Garantie annoncée au client', 'choice', True, '',
                     ['Décennale seule', '10 ans produit',
                      '15 ans produit', '20 ans produit'], ''),
                    ('Travaux supplémentaires possibles annoncés ?', 'yes_no',
                     True, '', [],
                     'Ce qui ne peut être su qu\'après dépose doit être dit '
                     'avant signature.'),
                ],
            },
            {
                'nom': 'Commande du matériel',
                'type': 'material_prep',
                'decalage': -7,
                'visible_client': False,
                'client_valide': False,
                'points': [
                    ('Complexe d\'étanchéité retenu', 'choice', True, '',
                     ['Bitume bicouche soudé', 'Bitume monocouche',
                      'EPDM', 'PVC', 'TPO', 'Résine polyuréthane',
                      'Système d\'étanchéité liquide', 'Asphalte'], ''),
                    ('Mode de fixation', 'choice', True, '',
                     ['Soudé en plein', 'Semi-indépendant',
                      'Fixation mécanique', 'Lestée', 'Collée'], ''),
                    ('Pare-vapeur prévu ?', 'yes_no', True, '', [],
                     'Son oubli fait condenser l\'eau dans l\'isolant : la '
                     'fuite vient de l\'intérieur et on cherche dehors.'),
                    ('Isolant retenu', 'choice', True, '',
                     ['Polyuréthane', 'Polystyrène expansé',
                      'Laine de roche', 'Verre cellulaire', 'Liège',
                      'Aucun'], ''),
                    ('Épaisseur d\'isolant', 'number', False, 'mm', [], ''),
                    ('Forme de pente à rapporter ?', 'yes_no', True, '', [],
                     'Si la pente mesurée est insuffisante.'),
                    ('Protection lourde prévue', 'choice', False, '',
                     ['Aucune', 'Gravillons', 'Dalles sur plots',
                      'Dalles scellées', 'Végétalisation'], ''),
                    ('Charge ajoutée au m²', 'number', False, 'kg', [],
                     'À vérifier contre la descente de charges : une '
                     'protection lourde de trop fissure la dalle.'),
                    ('Quantité commandée', 'number', True, 'm²', [], ''),
                    ('Fournisseur retenu', 'supplier', True, '', [],
                     'La fiche fournisseur : coordonnées et délai '
                     'annoncé viennent avec.'),
                    ('Devis de référence', 'quote', False, '', [],
                     'Le devis client que cette commande sert, pour '
                     'rapprocher la dépense de ce qui a été vendu.'),
                    ('Numéro de commande ou de devis fournisseur',
                     'text', False, '', [],
                     'La référence côté fournisseur, à rappeler en cas '
                     'de litige sur la livraison.'),
                    ('Commande passée le', 'date', True, '', [], ''),
                    ('Date de livraison annoncée', 'date', True, '', [], ''),
                    ('Livraison en toiture prévue ?', 'yes_no', True, '', [],
                     'Livrer au sol ce qui doit monter coûte une journée '
                     'd\'homme.'),
                    ('Monte-matériaux ou grue réservé le', 'date', False, '',
                     [], ''),
                    ('Nacelle réservée', 'yes_no', False, '', [], ''),
                    ('Échafaudage réservé', 'yes_no', False, '', [], ''),
                    ('Benne commandée', 'yes_no', True, '', [], ''),
                    ('Benne amiante séparée commandée ?', 'yes_no', False, '',
                     [], 'Si le diagnostic est positif.'),
                    ('Bâches de secours prévues ?', 'yes_no', True, '', [],
                     'Un toit ouvert et un orage : sans bâche sur place, '
                     'c\'est le logement du dessous qui paie.'),
                    ('Montant de la commande', 'number', False, '€', [], ''),
                ],
            },
            {
                'nom': 'Installation du chantier',
                'type': 'work_start',
                'decalage': 0,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Météo vérifiée sur les trois jours à venir ?', 'yes_no',
                     True, '', [], ''),
                    ('Protections collectives en place ?', 'yes_no', True, '',
                     [], ''),
                    ('Zone de stockage délimitée en toiture ?', 'yes_no',
                     True, '', [], ''),
                    ('Extincteurs en place ?', 'yes_no', True, '', [], ''),
                    ('Bâches de secours montées sur le toit ?', 'yes_no',
                     True, '', [],
                     'Sur le toit, pas dans le camion.'),
                    ('Locaux en dessous protégés ?', 'yes_no', True, '', [],
                     ''),
                    ('Matériel livré et contrôlé ?', 'yes_no', True, '', [],
                     ''),
                    ('Photo de l\'installation', 'photo', False, '', [], ''),
                ],
            },
            {
                'nom': 'Dépose de l\'ancienne étanchéité',
                'type': 'other',
                'decalage': 1,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Ancienne étanchéité déposée ?', 'yes_no', True, '', [],
                     ''),
                    ('Gravillons ou lestage évacués ?', 'yes_no', False, '',
                     [], ''),
                    ('État du support après dépose', 'choice', True, '',
                     ['Bon', 'À réparer ponctuellement', 'Fissuré',
                      'Humide', 'À reprendre entièrement'],
                     'Le moment de vérité : c\'est ici qu\'apparaît ce que '
                     'le sondage ne montrait pas.'),
                    ('Le support est-il SEC ?', 'yes_no', True, '', [],
                     'Poser sur un support humide, c\'est enfermer l\'eau '
                     'et refaire le toit dans trois ans.'),
                    ('Reprise du support nécessaire ?', 'yes_no', True, '',
                     [], ''),
                    ('Travaux supplémentaires à chiffrer ?', 'yes_no', True,
                     '', [],
                     'À dire au client AVANT de poser, pas sur la facture.'),
                    ('Lesquels', 'text', False, '', [], ''),
                    ('Photo du support nu', 'photo', True, '', [], ''),
                    ('Bordereau de suivi des déchets récupéré ?', 'yes_no',
                     False, '', [], ''),
                ],
            },
            {
                'nom': 'Pose du complexe',
                'type': 'fitting',
                'decalage': 3,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Pare-vapeur posé ?', 'yes_no', True, '', [], ''),
                    ('Isolant posé ?', 'yes_no', True, '', [], ''),
                    ('Forme de pente réalisée ?', 'yes_no', False, '', [], ''),
                    ('Première couche posée ?', 'yes_no', True, '', [], ''),
                    ('Deuxième couche ou membrane posée ?', 'yes_no', True,
                     '', [], ''),
                    ('Relevés traités ?', 'yes_no', True, '', [], ''),
                    ('Hauteur de relevé réalisée', 'number', True, 'cm', [],
                     'Au moins 15 cm au-dessus de la protection.'),
                    ('Engravures et bandes de solin posées ?', 'yes_no', True,
                     '', [], ''),
                    ('Toutes les traversées sont-elles traitées ?', 'yes_no',
                     True, '', [],
                     'Une seule oubliée suffit à refaire venir l\'équipe.'),
                    ('Nombre de traversées traitées', 'number', False, 'u',
                     [], ''),
                    ('Platines d\'évacuation posées ?', 'yes_no', True, '',
                     [], ''),
                    ('Trop-pleins posés ?', 'yes_no', True, '', [], ''),
                    ('Protection lourde mise en place ?', 'yes_no', False, '',
                     [], ''),
                    ('Photo des relevés terminés', 'photo', True, '', [], ''),
                    ('Photo des évacuations terminées', 'photo', True, '', [],
                     ''),
                ],
            },
            {
                'nom': 'Mise en eau et contrôles',
                'type': 'tests',
                'decalage': 6,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Mise en eau réalisée ?', 'yes_no', True, '', [],
                     'Le seul essai qui prouve l\'étanchéité. Sans elle, on '
                     'livre une promesse.'),
                    ('Durée de la mise en eau', 'number', False, 'h', [],
                     'Vingt-quatre heures au minimum.'),
                    ('Résultat de la mise en eau', 'choice', True, '',
                     ['Étanche', 'Fuite détectée et reprise',
                      'Fuite détectée, non reprise',
                      'Non réalisable — motif en commentaire'], ''),
                    ('Contrôle de toutes les soudures réalisé ?', 'yes_no',
                     True, '', [], ''),
                    ('Essai à la pointe sèche réalisé ?', 'yes_no', False, '',
                     [], ''),
                    ('L\'eau s\'écoule-t-elle vers les évacuations ?',
                     'yes_no', True, '', [], ''),
                    ('Reste-t-il des zones de stagnation ?', 'yes_no', True,
                     '', [],
                     'Si oui : à signaler par écrit au client, c\'est une '
                     'limite du support et non un défaut de pose.'),
                    ('Photo de la mise en eau', 'photo', True, '', [], ''),
                ],
            },
            {
                'nom': 'Nettoyage et évacuation',
                'type': 'cleaning',
                'decalage': 7,
                'visible_client': True,
                'client_valide': False,
                'points': [
                    ('Gravats évacués ?', 'yes_no', True, '', [], ''),
                    ('Bordereaux de déchets conservés ?', 'yes_no', True, '',
                     [], ''),
                    ('Évacuations dégagées et testées ?', 'yes_no', True, '',
                     [], ''),
                    ('Toiture et abords nettoyés ?', 'yes_no', True, '', [],
                     ''),
                    ('Protections provisoires retirées ?', 'yes_no', False,
                     '', [], ''),
                ],
            },
            {
                'nom': 'Réception du chantier',
                'type': 'reception',
                'decalage': 8,
                'visible_client': True,
                'client_valide': True,
                'points': [
                    ('Procès-verbal de réception signé ?', 'yes_no', True, '',
                     [], ''),
                    ('Réserves émises par le client', 'text', False, '', [],
                     'À reporter ensuite dans les réserves du chantier.'),
                    ('Attestation de garantie remise ?', 'yes_no', True, '',
                     [], ''),
                    ('Carnet d\'entretien remis ?', 'yes_no', True, '', [],
                     'Une étanchéité sans entretien perd sa garantie : le '
                     'remettre protège l\'entreprise autant que le client.'),
                    ('Fréquence d\'entretien expliquée au client ?', 'yes_no',
                     True, '', [],
                     'Deux visites par an, et après chaque gros coup de '
                     'vent.'),
                    ('Fiches techniques des produits remises ?', 'yes_no',
                     False, '', [], ''),
                    ('Plan de repérage des traversées remis ?', 'yes_no',
                     False, '', [],
                     'Utile à qui reviendra dans dix ans.'),
                    ('Photo du chantier terminé', 'photo', True, '', [], ''),
                ],
            },
        ],
    },
}


def catalogue_pour_affichage():
    """Le catalogue avec ses compteurs, pour la page des modèles.

    Les nombres sont calculés depuis la structure et jamais écrits à la
    main : un point ajouté ici changerait un chiffre affiché ailleurs, et
    c'est le genre d'écart que personne ne remarque avant qu'un client le
    relève.
    """
    liste = []
    for cle, modele in CATALOGUE_DES_MODELES.items():
        etapes = modele['etapes']
        points = [point for etape in etapes for point in etape['points']]
        liste.append({
            'cle': cle,
            'nom': modele['nom'],
            'description': modele['description'],
            'nombre_d_etapes': len(etapes),
            'nombre_de_points': len(points),
            # L'indice 2 du tuple est « obligatoire ». Voir le format en
            # tête de fichier.
            'nombre_d_importants': sum(1 for point in points if point[2]),
        })
    return liste


def installer_un_modele_pret(company, cle):
    """Crée dans cette entreprise le modèle décrit par `cle`.

    Retourne le ProjectTemplate créé, ou None si la clé est inconnue.

    Le nom est rendu libre s'il est déjà pris : installer deux fois ne doit
    pas échouer en IntegrityError sur `unique_together ['company', 'name']`,
    et surtout ne doit pas écraser un modèle que l'utilisateur a modifié —
    son travail compte plus que notre version d'origine.
    """
    from .models import (
        ProjectTemplate,
        ProjectTemplateItem,
        ProjectTemplateStep,
    )

    description = CATALOGUE_DES_MODELES.get(cle)
    if description is None:
        return None

    base = description['nom'][:150]
    nom = base
    rang = 2
    while ProjectTemplate.objects.filter(company=company, name=nom).exists():
        suffixe = f' ({rang})'
        nom = base[:150 - len(suffixe)] + suffixe
        rang += 1

    modele = ProjectTemplate.objects.create(
        company=company,
        name=nom,
        description=description['description'],
        # Par défaut seulement si l'entreprise n'en a pas déjà un : le
        # `save()` du modèle démettrait silencieusement celui en place.
        is_default=not ProjectTemplate.objects.filter(
            company=company, is_default=True).exists(),
        is_active=True,
    )

    for rang_etape, etape in enumerate(description['etapes'], start=1):
        creee = ProjectTemplateStep.objects.create(
            template=modele,
            name=etape['nom'],
            step_type=etape['type'],
            order=rang_etape,
            offset_days=etape['decalage'],
            visible_to_client=etape['visible_client'],
            client_can_validate=etape['client_valide'],
        )
        ProjectTemplateItem.objects.bulk_create([
            ProjectTemplateItem(
                step=creee,
                label=libelle,
                help_text=aide,
                answer_type=type_reponse,
                unit=unite,
                options=list(options),
                is_required=obligatoire,
                order=rang_point,
            )
            for rang_point, (libelle, type_reponse, obligatoire, unite,
                             options, aide)
            in enumerate(etape['points'], start=1)
        ])

    return modele
