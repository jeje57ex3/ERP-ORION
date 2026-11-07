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
}


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
