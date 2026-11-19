"""apps/fiscal_pt/coherence.py — Ce qu'un schéma ne sait pas dire.

POURQUOI CE MODULE EXISTE

Un XSD décrit une FORME : quels éléments, dans quel ordre, avec quelles
valeurs admises. Il ne sait pas dire que `GrossTotal` doit égaler
`NetTotal` plus `TaxPayable`, ni qu'un `ProductCode` employé sur une
ligne doit figurer dans le référentiel.

Le validateur de l'AT, lui, vérifie ces deux choses. Un fichier qui
passe le schéma et échoue ici est rejeté tout autant — et le motif du
rejet est alors bien plus difficile à comprendre, parce qu'il parle de
cohérence et non de structure.

LES DEUX FAMILLES DE CONTRÔLES

1. L'ARITHMÉTIQUE. Les totaux d'un document contre ses lignes, et les
   totaux du fichier contre ses documents. Un centime d'écart suffit à
   faire rejeter l'ensemble, et c'est l'erreur la plus courante : elle
   vient d'un cumul tenu à part qui a dérivé.

2. LE RÉFÉRENTIEL. Chaque `ProductCode`, chaque `CustomerID`, chaque
   couple (`TaxCode`, `TaxCountryRegion`) employé dans un document doit
   exister dans `MasterFiles`. C'est l'oubli le plus fréquent : les
   documents sont justes, le référentiel est incomplet, et le fichier est
   rejeté en entier.

LA TOLÉRANCE, ET POURQUOI ELLE N'EST PAS ZÉRO

La TVA d'un document se calcule ligne par ligne, et chaque ligne est
arrondie au centime. La somme des TVA arrondies diffère donc parfois
d'un centime de la TVA calculée sur le total — c'est de l'arithmétique,
pas une erreur. On tolère un centime PAR LIGNE, ce qui est la marge
qu'un arrondi peut réellement produire, et rien de plus : une tolérance
large laisserait passer une vraie incohérence.
"""

from decimal import Decimal, InvalidOperation

from .saft import ESPACE_DE_NOMS, TYPES_AU_DEBIT
from .schema import Anomalie

#: La tolérance d'arrondi, par ligne de document.
TOLERANCE_PAR_LIGNE = Decimal('0.01')

ZERO = Decimal('0.00')


def _etiquette(nom):
    return f'{{{ESPACE_DE_NOMS}}}{nom}'


def _texte(element, nom):
    if element is None:
        return None
    trouve = element.find(_etiquette(nom))
    return trouve.text if trouve is not None else None


def _montant(element, nom):
    """Un montant, ou None s'il est absent ou illisible.

    On rend None plutôt que zéro : un champ absent et un champ à zéro ne
    disent pas la même chose, et les confondre ferait passer un total
    manquant pour un total nul — donc équilibré.
    """
    brut = _texte(element, nom)
    if brut is None:
        return None
    try:
        return Decimal(brut.strip())
    except (InvalidOperation, AttributeError):
        return None


def _documents(racine):
    return racine.findall(
        f'{_etiquette("SourceDocuments")}/{_etiquette("SalesInvoices")}/'
        f'{_etiquette("Invoice")}')


def _referentiels(racine):
    """Les codes déclarés dans `MasterFiles`, pour vérifier les renvois."""
    referentiels = racine.find(_etiquette('MasterFiles'))
    if referentiels is None:
        return set(), set(), set()

    clients = {_texte(c, 'CustomerID')
               for c in referentiels.findall(_etiquette('Customer'))}
    produits = {_texte(p, 'ProductCode')
                for p in referentiels.findall(_etiquette('Product'))}
    taux = {(_texte(t, 'TaxCode'), _texte(t, 'TaxCountryRegion'))
            for t in referentiels.findall(
                f'{_etiquette("TaxTable")}/{_etiquette("TaxTableEntry")}')}

    return clients, produits, taux


# ── L'arithmétique d'un document ─────────────────────────────────────────────

def _verifier_un_document(document, anomalies):
    numero = _texte(document, 'InvoiceNo') or '(sans numéro)'
    type_document = _texte(document, 'InvoiceType') or ''
    au_debit = type_document in TYPES_AU_DEBIT

    totaux = document.find(_etiquette('DocumentTotals'))
    net = _montant(totaux, 'NetTotal')
    taxe = _montant(totaux, 'TaxPayable')
    brut = _montant(totaux, 'GrossTotal')

    if None in (net, taxe, brut):
        anomalies.append(Anomalie(
            numero, 'Un total du document est absent ou illisible : '
                    'la cohérence ne peut pas être vérifiée.'))
        return

    # 1. GrossTotal = NetTotal + TaxPayable. Exactement.
    #
    # Aucune tolérance ici : les trois nombres sont écrits par nous, et un
    # écart signifie que l'un des trois a été calculé autrement que les
    # autres.
    if brut != net + taxe:
        anomalies.append(Anomalie(
            numero,
            f'GrossTotal ({brut}) ne vaut pas NetTotal + TaxPayable '
            f'({net} + {taxe} = {net + taxe}).'))

    lignes = document.findall(_etiquette('Line'))
    if not lignes:
        anomalies.append(Anomalie(numero, 'Document sans ligne.'))
        return

    champ = 'DebitAmount' if au_debit else 'CreditAmount'
    somme = ZERO
    taxe_attendue = ZERO
    manquants = 0

    for rang, ligne in enumerate(lignes, start=1):
        montant = _montant(ligne, champ)
        if montant is None:
            manquants += 1
            # Le montant est peut-être du mauvais côté : c'est une erreur
            # bien plus parlante que « total incohérent ».
            autre = 'CreditAmount' if au_debit else 'DebitAmount'
            if _montant(ligne, autre) is not None:
                anomalies.append(Anomalie(
                    f'{numero} ligne {rang}',
                    f'Montant porté en {autre} alors qu’un document '
                    f'« {type_document} » l’attend en {champ}. Le fichier '
                    's’équilibrerait à l’envers, et le validateur de l’AT '
                    'ne le dit pas : seul le contrôle le relève.'))
            continue

        somme += montant

        taux = _montant(ligne.find(_etiquette('Tax')), 'TaxPercentage')
        if taux is not None:
            taxe_attendue += (montant * taux / Decimal('100')).quantize(
                Decimal('0.01'))

    if manquants:
        return

    # 2. NetTotal = somme des montants de lignes. Exactement, là encore.
    if somme != net:
        anomalies.append(Anomalie(
            numero,
            f'NetTotal ({net}) ne vaut pas la somme des {len(lignes)} '
            f'ligne(s) ({somme}). Un cumul tenu à part a dérivé.'))

    # 3. TaxPayable contre la TVA recalculée, à l'arrondi près.
    tolerance = TOLERANCE_PAR_LIGNE * len(lignes)
    if abs(taxe - taxe_attendue) > tolerance:
        anomalies.append(Anomalie(
            numero,
            f'TaxPayable ({taxe}) s’écarte de la TVA recalculée depuis les '
            f'lignes ({taxe_attendue}) de plus que l’arrondi ne permet '
            f'({tolerance}).'))


# ── Les totaux du fichier ────────────────────────────────────────────────────

def _verifier_les_totaux_du_fichier(racine, documents, anomalies):
    ventes = racine.find(
        f'{_etiquette("SourceDocuments")}/{_etiquette("SalesInvoices")}')
    if ventes is None:
        return

    annonce = _texte(ventes, 'NumberOfEntries')
    if annonce is not None and annonce.strip() != str(len(documents)):
        anomalies.append(Anomalie(
            'SalesInvoices',
            f'NumberOfEntries annonce {annonce.strip()} document(s) et le '
            f'fichier en contient {len(documents)}.'))

    credit = ZERO
    debit = ZERO
    for document in documents:
        net = _montant(document.find(_etiquette('DocumentTotals')),
                       'NetTotal')
        if net is None:
            continue
        if (_texte(document, 'InvoiceType') or '') in TYPES_AU_DEBIT:
            debit += net
        else:
            credit += net

    for nom, calcule in (('TotalCredit', credit), ('TotalDebit', debit)):
        annonce = _montant(ventes, nom)
        if annonce is None:
            anomalies.append(Anomalie('SalesInvoices',
                                      f'{nom} est absent ou illisible.'))
        elif annonce != calcule:
            anomalies.append(Anomalie(
                'SalesInvoices',
                f'{nom} annonce {annonce} et la somme des documents donne '
                f'{calcule}.'))


# ── Le référentiel ───────────────────────────────────────────────────────────

def _verifier_les_renvois(racine, documents, anomalies):
    clients, produits, taux = _referentiels(racine)

    for document in documents:
        numero = _texte(document, 'InvoiceNo') or '(sans numéro)'

        client = _texte(document, 'CustomerID')
        if client and client not in clients:
            anomalies.append(Anomalie(
                numero,
                f'Le client « {client} » n’est pas déclaré dans '
                'MasterFiles. Les documents sont justes, le référentiel est '
                'incomplet, et le fichier est rejeté en entier.'))

        for rang, ligne in enumerate(document.findall(_etiquette('Line')),
                                     start=1):
            produit = _texte(ligne, 'ProductCode')
            if produit and produit not in produits:
                anomalies.append(Anomalie(
                    f'{numero} ligne {rang}',
                    f'Le produit « {produit} » n’est pas déclaré dans '
                    'MasterFiles.'))

            taxe = ligne.find(_etiquette('Tax'))
            couple = (_texte(taxe, 'TaxCode'), _texte(taxe, 'TaxCountryRegion'))
            if couple[0] and couple not in taux:
                anomalies.append(Anomalie(
                    f'{numero} ligne {rang}',
                    f'Le taux « {couple[0]} » en région « {couple[1]} » '
                    'n’est pas déclaré dans la table des taux.'))


# ── Les dates et la période ──────────────────────────────────────────────────

def _verifier_les_dates(racine, documents, anomalies):
    entete = racine.find(_etiquette('Header'))
    debut = _texte(entete, 'StartDate')
    fin = _texte(entete, 'EndDate')

    for document in documents:
        numero = _texte(document, 'InvoiceNo') or '(sans numéro)'
        date_document = _texte(document, 'InvoiceDate')

        if not date_document:
            continue

        # Les dates ISO se comparent correctement comme du texte.
        if debut and date_document < debut:
            anomalies.append(Anomalie(
                numero, f'Daté du {date_document}, avant le début de la '
                        f'période ({debut}).'))
        if fin and date_document > fin:
            anomalies.append(Anomalie(
                numero, f'Daté du {date_document}, après la fin de la '
                        f'période ({fin}).'))

        # La PÉRIODE est le mois du document.
        #
        # Une période fausse ne casse ni le schéma ni l'arithmétique :
        # elle range le document dans le mauvais mois, et l'écart
        # n'apparaît qu'au rapprochement des déclarations de TVA.
        periode = _texte(document, 'Period')
        attendue = date_document[5:7].lstrip('0')
        if periode and periode.strip().lstrip('0') != attendue:
            anomalies.append(Anomalie(
                numero,
                f'Period vaut {periode.strip()} alors que le document est '
                f'daté du {date_document} (mois {attendue}).'))

        # L'horodatage d'enregistrement ne peut pas précéder la date du
        # document : un document enregistré avant d'exister est le signe
        # d'une antidate, et c'est ce que la chaîne de signatures sert à
        # empêcher.
        horodatage = _texte(document, 'SystemEntryDate')
        if horodatage and horodatage[:10] < date_document:
            anomalies.append(Anomalie(
                numero,
                f'Enregistré le {horodatage[:10]}, avant sa propre date '
                f'({date_document}).'))


# ── L'entrée publique ────────────────────────────────────────────────────────

def verifier(racine):
    """Les incohérences d'un fichier déjà conforme au schéma.

    `racine` est un `Element` déjà analysé. On ne reprend pas l'analyse du
    XML ici : ce module s'emploie APRÈS `schema.valider`, qui a déjà dit
    si le fichier était lisible et bien formé. Le rappeler donnerait deux
    messages pour un seul défaut.
    """
    anomalies = []
    documents = _documents(racine)

    for document in documents:
        _verifier_un_document(document, anomalies)

    _verifier_les_totaux_du_fichier(racine, documents, anomalies)
    _verifier_les_renvois(racine, documents, anomalies)
    _verifier_les_dates(racine, documents, anomalies)

    return anomalies


def resume(anomalies):
    if not anomalies:
        return ('Cohérence vérifiée : totaux, référentiel, dates et '
                'périodes s’accordent.')
    nombre = len(anomalies)
    return (f'{nombre} incohérence{"s" if nombre > 1 else ""}. Un fichier '
            'conforme au schéma mais incohérent est rejeté tout autant, et '
            'le motif du rejet est plus difficile à comprendre.')
