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

from decimal import Decimal

from django.core.exceptions import ValidationError

from . import saft
from .models import DocumentFiscal, ParametresFiscauxPT
from .taxas import PALIERS_PAR_REGION


def _client_du_document(document):
    """L'identifiant et le nom du client, tels qu'ils figureront au SAF-T.

    Un document sans NIF d'acquéreur est une vente au consommateur final :
    le schéma impose alors le NIF conventionnel et un client générique,
    pas un champ vide.
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
    """Les quatre jeux de données du SAF-T, pour la période donnée."""
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
            'motif': document.motif_rectification,
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

    # La table des taux doit couvrir tous les codes employés. On l'enrichit
    # des paliers de la région même s'ils n'ont pas servi : le validateur
    # accepte une table plus large, jamais une table incomplète.
    for region_vue in {region for _, region in taux}:
        for taux_connu, nom in PALIERS_PAR_REGION.get(region_vue, {}).items():
            code = saft.CODES_DE_TAUX[nom]
            taux.setdefault((code, region_vue), taux_connu)

    table = [(code, pourcentage, region)
             for (code, region), pourcentage in sorted(taux.items())]

    return entete, list(clients.values()), list(produits.values()), table, sortie


def composer(company, debut, fin):
    """Le fichier SAF-T de la période, en octets."""
    entete, clients, produits, taux, documents = rassembler(company, debut, fin)
    return saft.composer(entete, clients, produits, taux, documents)


def nom_de_fichier(company, debut, fin):
    """Le nom du fichier, lisible et daté.

    L'AT ne normalise pas le nom ; on le rend donc parlant, parce qu'un
    fichier remis par courriel qui s'appellerait « saft.xml » se confondra
    avec les onze précédents.
    """
    nif = ParametresFiscauxPT.de(company).nif or 'sem-nif'
    return f'SAFT-PT_{nif}_{debut:%Y%m%d}-{fin:%Y%m%d}.xml'
