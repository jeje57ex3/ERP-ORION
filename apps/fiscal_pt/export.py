"""apps/fiscal_pt/export.py — Assembler le SAF-T depuis la base.

Le module `saft` compose le XML à partir de dictionnaires ; celui-ci les
remplit depuis les documents enregistrés. La séparation permet de tester
la composition contre le schéma sans base de données, et le
rassemblement sans réécrire le XML.

TOUT VIENT DES DOCUMENTS FISCAUX, RIEN DES FACTURES D'ORIGINE

Les lignes ont été figées à l'émission. On ne relit donc jamais la
facture de l'ERP : elle a pu changer depuis, et le fichier remis à
l'administration doit correspondre à la signature qui l'accompagne, pas
à l'état actuel du dossier.
"""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError

from . import saft
from .models import (DocumentDeTravailFiscal, DocumentFiscal,
                     MouvementFiscal, ParametresFiscauxPT,
                     RecuFiscal)
from .taxas import PALIERS_PAR_REGION

#: `SourceID` — l'utilisateur qui a émis le document. Le schéma le veut
#: dans les quatre tables, et les documents ne le stockent pas : les
#: factures employaient déjà la valeur de repli de `saft.py`. On la nomme
#: ici pour que les quatre tables du MÊME fichier déclarent la même
#: chose, au lieu que deux d'entre elles l'exigent et que les deux autres
#: la devinent.
OPERATEUR = 'Orion'


def _client_du_document(document):
    """L'identifiant et le nom du client, tels qu'ils figureront au SAF-T.

    Un document sans NIF d'acquéreur est une vente au consommateur final :
    le schéma impose alors le NIF conventionnel et un client générique,
    pas un champ vide.

    Sert aux documents de facturation COMME aux reçus : les deux portent
    un NIF d'acquéreur et un lien vers la facture d'origine, et les deux
    doivent désigner le même `CustomerID` — sans quoi le reçu renverrait à
    un client que `MasterFiles` ne déclare pas.
    """
    if not document.nif_acquereur:
        return (saft.CLIENT_CONSOMMATEUR_FINAL, saft.CLIENT_CONSOMMATEUR_FINAL,
                saft.NIF_CONSOMMATEUR_FINAL)

    nom = ''
    if document.source_app == 'sales' and document.source_id:
        from apps.sales.models import Invoice
        facture = Invoice.objects.filter(pk=document.source_id).first()
        if facture:
            nom = facture.customer.name

    identifiant = f'C{document.nif_acquereur}'
    return identifiant, (nom or identifiant), document.nif_acquereur


def rassembler(company, debut, fin):
    """Les cinq jeux de données du SAF-T, pour la période donnée."""
    parametres = ParametresFiscauxPT.de(company)
    if not parametres.nif:
        raise ValidationError(
            'Le NIF de l’entreprise est absent. Renseignez-le dans '
            'Paramètres → Conformité Portugal : il figure dans l’en-tête du '
            'SAF-T, et un fichier sans lui est rejeté en entier.')

    documents = (DocumentFiscal.objects
                 .filter(company=company,
                         date_document__gte=debut, date_document__lte=fin)
                 .select_related('serie', 'document_rectifie')
                 .order_by('date_document', 'numero_sequentiel'))

    recus = (RecuFiscal.objects
             .filter(company=company,
                     date_document__gte=debut, date_document__lte=fin)
             .select_related('serie')
             .order_by('date_document', 'numero_sequentiel'))

    # LES TABLES 4.2 ET 4.3, QUE RIEN NE LISAIT.
    #
    # `saft.py` sait les composer depuis des dictionnaires, et un test les
    # valide contre le XSD. Mais la lecture en base n'existait pas : le
    # fichier reellement produit par l'ecran d'export ne portait aucun
    # document de transport ni aucun devis, alors que l'entreprise en
    # emet. Un fichier remis a l'AT declarait donc une activite sans ses
    # documents de circulation.
    mouvements = (MouvementFiscal.objects
                  .filter(company=company,
                          date_document__gte=debut, date_document__lte=fin)
                  .select_related('serie')
                  .order_by('date_document', 'numero_sequentiel'))

    travaux = (DocumentDeTravailFiscal.objects
               .filter(company=company,
                       date_document__gte=debut, date_document__lte=fin)
               .select_related('serie')
               .order_by('date_document', 'numero_sequentiel'))

    entete = {
        'nif': parametres.nif,
        'nom': company.name,
        'exercice': str(debut.year),
        'debut': debut,
        'fin': fin,
        'adresse': {
            'adresse': getattr(company, 'address', '') or 'Desconhecido',
            'ville': getattr(company, 'city', '') or 'Desconhecido',
            'code_postal': getattr(company, 'postal_code', '') or '0000-000',
            'pays': 'PT',
        },
        'numero_de_certificat': parametres.numero_de_certificat or '0',
        'nif_editeur': parametres.nif_editeur or parametres.nif,
        'produit': f'Orion ERP/{parametres.nom_editeur}',
        'version_produit': parametres.version_produit,
    }

    clients = {}
    produits = {}
    taux = {}
    sortie = []

    for document in documents:
        identifiant, nom, nif = _client_du_document(document)
        clients.setdefault(identifiant, {
            'identifiant': identifiant, 'nom': nom, 'nif': nif,
            'adresse': {'adresse': 'Desconhecido', 'ville': 'Desconhecido',
                        'code_postal': '0000-000', 'pays': 'PT'},
        })

        region = document.serie.region

        # La référence au document rectifié est portée par LE DOCUMENT, et
        # recopiée sur chaque ligne parce que c'est là que le SAF-T
        # l'attend. La stocker une fois et la distribuer ici évite de la
        # dupliquer dans les lignes figées, où elle pourrait diverger.
        rectifie = (document.document_rectifie.numero
                    if document.document_rectifie_id else '')
        lignes = []

        for figee in document.lignes:
            code = figee['code_produit']
            produits.setdefault(code, {
                'code': code,
                'description': figee['description'],
            })

            code_de_taux = figee['code_de_taux']
            taux.setdefault((code_de_taux, region), Decimal(figee['taux']))

            lignes.append({
                'code_produit': code,
                'description': figee['description'],
                'quantite': figee['quantite'],
                'unite': figee['unite'],
                'prix_unitaire': figee['prix_unitaire'],
                'montant': figee['base'],
                'taux': figee['taux'],
                'code_de_taux': code_de_taux,
                'region': region,
                'date': document.date_document,
                'motif_exoneration': figee.get('motif_exoneration') or '',
                'code_exoneration': figee.get('code_exoneration') or '',
                'document_rectifie': rectifie,
                'motif_rectification': document.motif_rectification,
            })

        sortie.append({
            'numero': document.numero,
            'atcud': document.atcud,
            'signature': document.signature,
            'version_cle': document.version_cle,
            'date': document.date_document,
            'type': document.serie.type_document,
            'etat': document.etat,
            # LE MOTIF DE L'ETAT, ET NON CELUI DE LA RECTIFICATION.
            #
            # Ce champ alimente « Reason » DANS `DocumentStatus` : il dit
            # pourquoi le document est dans cet etat -- pourquoi il a ete
            # annule. On y passait `motif_rectification`, qui dit pourquoi
            # un AVOIR rectifie une facture : deux informations
            # differentes, declarees au meme endroit. La rectification a
            # sa place a elle, dans le bloc `References` de la ligne, ou
            # `saft.references()` la pose deja.
            'motif': document.motif_etat,
            'date_etat': document.etat_change_le,
            'horodatage': document.horodatage,
            'client': identifiant,
            'lignes': lignes,
            # Les paiements figés, comme les lignes : le fichier doit dire
            # ce que le document atteste, et non ce que la trésorerie
            # pense aujourd'hui du règlement.
            'paiements': document.paiements or [],
            'total_base': document.total_base,
            'total_taxes': document.total_taxes,
            'total': document.total,
        })

    # LES REÇUS, APRÈS LES DOCUMENTS ET POUR UNE RAISON.
    #
    # Un reçu n'ajoute ni produit ni taux au référentiel — il n'a ni ligne
    # de produit ni taux de TVA. Il ajoute en revanche un CLIENT, et il
    # faut qu'il tombe sur le MÊME identifiant que la facture qu'il règle :
    # c'est pourquoi les deux passent par `_client_du_document`, et non par
    # deux calculs qui se ressembleraient.
    sortie_des_recus = []

    for recu in recus:
        identifiant, nom, nif = _client_du_document(recu)
        clients.setdefault(identifiant, {
            'identifiant': identifiant, 'nom': nom, 'nif': nif,
            'adresse': {'adresse': 'Desconhecido', 'ville': 'Desconhecido',
                        'code_postal': '0000-000', 'pays': 'PT'},
        })

        sortie_des_recus.append({
            'numero': recu.numero,
            'atcud': recu.atcud,
            'date': recu.date_document,
            'type': recu.serie.type_document,
            'etat': recu.etat,
            'motif': recu.motif_etat,
            'date_etat': recu.etat_change_le,
            'horodatage': recu.horodatage,
            'client': identifiant,
            'affectations': [{
                'document': affectation['document'],
                'date': affectation['date'],
                'montant': affectation['montant'],
                'au_debit': affectation.get('au_debit', False),
                'description': affectation.get('description') or '',
            } for affectation in (recu.affectations or [])],
            'paiements': recu.paiements or [],
            'total_base': recu.total_base,
            'total_taxes': recu.total_taxes,
            'total': recu.total,
        })

    # ── Les mouvements de marchandises (table 4.2) ──────────────────────
    #
    # LEURS LIGNES ENRICHISSENT LE MÊME RÉFÉRENTIEL. Un produit transporté
    # et un taux appliqué sur un bon de livraison doivent figurer dans
    # `MasterFiles` comme ceux d'une facture : le validateur refuse un
    # `ProductCode` ou un `TaxCode` qu'aucune table ne déclare, et il ne
    # dit pas lequel des quatre blocs de documents l'a employé.
    sortie_des_mouvements = []
    fournisseurs = {}

    for mouvement in mouvements:
        region = mouvement.serie.region

        # LE CLIENT D'UN MOUVEMENT N'EST PAS CELUI D'UNE FACTURE.
        #
        # `_client_du_document` déduit l'identifiant du NIF ; ici
        # l'identifiant est saisi tel quel, parce que le schéma place
        # `CustomerID` et `SupplierID` dans un choix obligatoire et qu'un
        # mouvement peut désigner un fournisseur, cas qu'une facture ne
        # connaît pas. On déclare donc le tiers sous l'identifiant
        # réellement écrit dans le document — sans quoi le fichier
        # renverrait à un client absent de `MasterFiles`.
        tiers = (mouvement.identifiant_client
                 or mouvement.identifiant_fournisseur)
        adresse = {'adresse': 'Desconhecido', 'ville': 'Desconhecido',
                   'code_postal': '0000-000',
                   'pays': mouvement.pays_acquereur or 'PT'}

        if mouvement.identifiant_client:
            clients.setdefault(tiers, {
                'identifiant': tiers,
                'nom': tiers,
                'nif': mouvement.nif_acquereur or saft.NIF_CONSOMMATEUR_FINAL,
                'adresse': adresse,
            })
        else:
            # UN FOURNISSEUR, ET NON UN CLIENT DE PLUS.
            #
            # `StockMovement` place les deux dans un choix obligatoire, et
            # `MasterFiles` a une table pour chacun. Déclarer un
            # fournisseur parmi les clients ferait un fichier dont le
            # `SupplierID` ne renvoie à rien.
            #
            # Et pas de repli sur « 999999990 » : ce NIF désigne un
            # acheteur anonyme, ce qu'un fournisseur n'est jamais.
            fournisseurs.setdefault(tiers, {
                'identifiant': tiers,
                'nom': tiers,
                'nif': mouvement.nif_acquereur or 'Desconhecido',
                'adresse': adresse,
            })

        lignes = []
        for figee in mouvement.lignes:
            code = figee.get('reference') or figee['designation'][:50]
            produits.setdefault(code, {
                'code': code,
                'description': figee['designation'],
            })

            propre = {
                'reference': code,
                'designation': figee['designation'],
                'quantite': Decimal(figee['quantite']),
                'unite': figee.get('unite') or 'UN',
                'prix_unitaire': Decimal(figee['prix_unitaire']),
                'montant': Decimal(figee['montant']),
                'description': figee.get('description') or '',
                'region': region,
            }
            if figee.get('taux') is not None:
                propre['taux'] = Decimal(figee['taux'])
                propre['code_de_taux'] = figee.get('code_de_taux') or 'NOR'
                taux.setdefault((propre['code_de_taux'], region),
                                propre['taux'])
            if figee.get('motif_exoneration'):
                propre['motif_exoneration'] = figee['motif_exoneration']
                propre['code_exoneration'] = figee.get('code_exoneration') or ''
            lignes.append(propre)

        sortie_des_mouvements.append({
            'numero': mouvement.numero,
            'atcud': mouvement.atcud,
            'signature': mouvement.signature,
            'version_cle': mouvement.version_cle,
            'date': mouvement.date_document,
            'type_mouvement': mouvement.type_mouvement,
            'etat': mouvement.etat,
            'motif_etat': mouvement.motif_etat,
            'date_etat': mouvement.etat_change_le,
            'horodatage': mouvement.horodatage,
            'emetteur': OPERATEUR,
            'client': mouvement.identifiant_client or None,
            'fournisseur': mouvement.identifiant_fournisseur or None,
            'debut_transport': mouvement.debut_transport,
            'fin_transport': mouvement.fin_transport,
            'origine_envoi': mouvement.origine_envoi or None,
            'destination': mouvement.destination or None,
            'commentaire': mouvement.commentaire,
            'lignes': lignes,
            'total_base': mouvement.total_base,
            'total_taxes': mouvement.total_taxes,
            'total': mouvement.total,
        })

    # ── Les documents de travail (table 4.3) ────────────────────────────
    #
    # `CustomerID` y est unique et obligatoire — pas de choix avec un
    # fournisseur. Et `TaxPointDate` est exigé sur chaque ligne dans cette
    # table seule : à défaut de date figée, la date du document, qui est la
    # réponse juste dans la quasi-totalité des cas.
    sortie_des_travaux = []

    for travail in travaux:
        region = travail.serie.region
        identifiant = travail.identifiant_client

        clients.setdefault(identifiant, {
            'identifiant': identifiant,
            'nom': identifiant,
            'nif': travail.nif_acquereur or saft.NIF_CONSOMMATEUR_FINAL,
            'adresse': {'adresse': 'Desconhecido', 'ville': 'Desconhecido',
                        'code_postal': '0000-000',
                        'pays': travail.pays_acquereur or 'PT'},
        })

        lignes = []
        for figee in travail.lignes:
            code = figee.get('reference') or figee['designation'][:50]
            produits.setdefault(code, {
                'code': code,
                'description': figee['designation'],
            })

            propre = {
                'reference': code,
                'designation': figee['designation'],
                'quantite': Decimal(figee['quantite']),
                'unite': figee.get('unite') or 'UN',
                'prix_unitaire': Decimal(figee['prix_unitaire']),
                'montant': Decimal(figee['montant']),
                'description': figee.get('description') or '',
                'region': region,
                'date_tva': (date.fromisoformat(figee['date_tva'])
                             if figee.get('date_tva')
                             else travail.date_document),
            }
            if figee.get('taux') is not None:
                propre['taux'] = Decimal(figee['taux'])
                propre['code_de_taux'] = figee.get('code_de_taux') or 'NOR'
                taux.setdefault((propre['code_de_taux'], region),
                                propre['taux'])
            if figee.get('motif_exoneration'):
                propre['motif_exoneration'] = figee['motif_exoneration']
                propre['code_exoneration'] = figee.get('code_exoneration') or ''
            lignes.append(propre)

        sortie_des_travaux.append({
            'numero': travail.numero,
            'atcud': travail.atcud,
            'signature': travail.signature,
            'version_cle': travail.version_cle,
            'date': travail.date_document,
            'type_travail': travail.type_travail,
            'etat': travail.etat,
            'motif_etat': travail.motif_etat,
            'date_etat': travail.etat_change_le,
            'horodatage': travail.horodatage,
            'emetteur': OPERATEUR,
            'client': identifiant,
            'lignes': lignes,
            'total_base': travail.total_base,
            'total_taxes': travail.total_taxes,
            'total': travail.total,
        })

    # La table des taux doit couvrir tous les codes employés. On l'enrichit
    # des paliers de la région même s'ils n'ont pas servi : le validateur
    # accepte une table plus large, jamais une table incomplète.
    for region_vue in {region for _, region in taux}:
        for taux_connu, nom in PALIERS_PAR_REGION.get(region_vue, {}).items():
            code = saft.CODES_DE_TAUX[nom]
            taux.setdefault((code, region_vue), taux_connu)

    table = [(code, pourcentage, region)
             for (code, region), pourcentage in sorted(taux.items())]

    return (entete, list(clients.values()), list(produits.values()), table,
            sortie, sortie_des_recus, sortie_des_mouvements,
            sortie_des_travaux, list(fournisseurs.values()))


def composer(company, debut, fin):
    """Le fichier SAF-T de la période, en octets."""
    (entete, clients, produits, taux, documents, recus, mouvements,
     travaux, fournisseurs) = rassembler(company, debut, fin)
    return saft.composer(entete, clients, produits, taux, documents, recus,
                         mouvements, travaux, fournisseurs)


def nom_de_fichier(company, debut, fin):
    """Le nom du fichier, lisible et daté.

    L'AT ne normalise pas le nom ; on le rend donc parlant, parce qu'un
    fichier remis par courriel qui s'appellerait « saft.xml » se confondra
    avec les onze précédents.
    """
    nif = ParametresFiscauxPT.de(company).nif or 'sem-nif'
    return f'SAFT-PT_{nif}_{debut:%Y%m%d}-{fin:%Y%m%d}.xml'
