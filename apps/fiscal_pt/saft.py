"""apps/fiscal_pt/saft.py — L'export SAF-T (PT).

CE QUE C'EST

Le fichier normalisé que l'entreprise remet à l'administration
portugaise : en-tête, référentiels, et tous les documents de facturation
de la période. Portaria n.º 302/2016 pour la version 1.04_01, qui est
celle en vigueur pour la facturation.

LA CONTRAINTE QUI GOUVERNE TOUT CE MODULE : L'ORDRE

Le schéma XSD de l'AT décrit chaque bloc comme une SÉQUENCE. Les
éléments doivent donc apparaître dans l'ordre exact du schéma — pas dans
l'ordre où on les a sous la main, pas dans un ordre alphabétique. Un
seul élément déplacé fait rejeter le fichier ENTIER, et le message du
validateur désigne l'élément suivant, pas celui qui manque. C'est
pourquoi l'ordre est écrit ici une fois, explicitement, sous forme de
listes nommées : il se relit contre le schéma sans avoir à suivre le
code.

CE QUE CE MODULE NE FAIT PAS

Il n'exporte pas la comptabilité (TaxAccountingBasis « C »), ni les
documents de mouvement de marchandises (MovementOfGoods), ni les
documents de travail (WorkingDocuments). Il couvre la facturation —
« F » —, qui est le périmètre de la certification d'un logiciel de
facturation : la table 4.1 des documents de vente et la table 4.4 des
reçus.

LA TABLE 4.4 N'EST PAS LA TABLE 4.1 AVEC D'AUTRES NOMS

Sa ligne n'a pas de produit, son état s'appelle autrement et n'admet que
deux valeurs, son moyen de paiement porte un autre nom d'élément pour le
même type, et ses totaux rangent « Settlement » AVANT « Currency » au
lieu de l'inverse. Aucune liste d'ordre ne peut donc être reprise de
l'une à l'autre, et c'est pourquoi elles sont écrites séparément plutôt
que dérivées.
"""

from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree as ET

from . import tipos

VERSION = '1.04_01'
ESPACE_DE_NOMS = 'urn:OECD:StandardAuditFile-Tax:PT_1.04_01'

#: « F » = facturation seule. « C » serait la comptabilité, « I » les deux.
BASE_COMPTABLE = 'F'

#: Les codes de taux du SAF-T, et le palier de `taxas` auquel ils répondent.
CODES_DE_TAUX = {
    'normal': 'NOR',
    'intermedia': 'INT',
    'reduzida': 'RED',
    'isenta': 'ISE',
}

LIBELLES_DE_TAUX = {
    'NOR': 'Taxa normal',
    'INT': 'Taxa intermédia',
    'RED': 'Taxa reduzida',
    'ISE': 'Isenta',
}

#: Le NIF conventionnel du consommateur final, et son identifiant client.
NIF_CONSOMMATEUR_FINAL = '999999990'
CLIENT_CONSOMMATEUR_FINAL = 'Consumidor final'

#: L'ordre des éléments, tel que le schéma les énumère.
#:
#: Ces listes ne sont pas recopiées à l'aveugle : `tests/
#: test_fiscal_pt_schema.py` les compare une par une au fichier XSD de
#: l'AT, versé dans `schemas/SAFTPT1.04_01.xsd`. Un élément ajouté ici au
#: mauvais rang, ou un élément que le schéma déplacerait dans une version
#: future, se voit donc au test et non à la remise du fichier.
ORDRE_ADRESSE = ('BuildingNumber', 'StreetName', 'AddressDetail', 'City',
                 'PostalCode', 'Region', 'Country')

ORDRE_ENTETE = ('AuditFileVersion', 'CompanyID', 'TaxRegistrationNumber',
                'TaxAccountingBasis', 'CompanyName', 'BusinessName',
                'CompanyAddress', 'FiscalYear', 'StartDate', 'EndDate',
                'CurrencyCode', 'DateCreated', 'TaxEntity',
                'ProductCompanyTaxID', 'SoftwareCertificateNumber',
                'ProductID', 'ProductVersion', 'HeaderComment', 'Telephone',
                'Fax', 'Email', 'Website')

ORDRE_CLIENT = ('CustomerID', 'AccountID', 'CustomerTaxID', 'CompanyName',
                'Contact', 'BillingAddress', 'ShipToAddress', 'Telephone',
                'Fax', 'Email', 'Website', 'SelfBillingIndicator')

ORDRE_PRODUIT = ('ProductType', 'ProductCode', 'ProductGroup',
                 'ProductDescription', 'ProductNumberCode',
                 'CustomsDetails')

ORDRE_TAUX = ('TaxType', 'TaxCountryRegion', 'TaxCode', 'Description',
              'TaxExpirationDate', 'TaxPercentage', 'TaxAmount')

ORDRE_ETAT = ('InvoiceStatus', 'InvoiceStatusDate', 'Reason', 'SourceID',
              'SourceBilling')

ORDRE_REGIMES = ('SelfBillingIndicator', 'CashVATSchemeIndicator',
                 'ThirdPartiesBillingIndicator')

ORDRE_DOCUMENT = ('InvoiceNo', 'ATCUD', 'DocumentStatus', 'Hash',
                  'HashControl', 'Period', 'InvoiceDate', 'InvoiceType',
                  'SpecialRegimes', 'SourceID', 'EACCode', 'SystemEntryDate',
                  'TransactionID', 'CustomerID', 'ShipTo', 'ShipFrom',
                  'MovementEndTime', 'MovementStartTime', 'Line',
                  'DocumentTotals', 'WithholdingTax')

ORDRE_LIGNE = ('LineNumber', 'OrderReferences', 'ProductCode',
               'ProductDescription', 'Quantity', 'UnitOfMeasure', 'UnitPrice',
               'TaxBase', 'TaxPointDate', 'References', 'Description',
               'ProductSerialNumber', 'DebitAmount', 'CreditAmount', 'Tax',
               'TaxExemptionReason', 'TaxExemptionCode', 'SettlementAmount',
               'CustomsInformation')

ORDRE_TAXE_DE_LIGNE = ('TaxType', 'TaxCountryRegion', 'TaxCode',
                       'TaxPercentage', 'TaxAmount')

ORDRE_TOTAUX = ('TaxPayable', 'NetTotal', 'GrossTotal', 'Currency',
                'Settlement', 'Payment')

#: Les types de documents qui portent un montant au DÉBIT et non au crédit.
#: Une note de crédit inversée dans les totaux fait un fichier qui s'équilibre
#: à l'envers, et le validateur ne le dit pas : il accepte.
#:
#: CETTE LISTE NE DIT QUE LE SENS. Celle des documents qui doivent DÉSIGNER
#: la facture qu'ils rectifient est `tipos.TYPES_RECTIFICATIFS`, et elle est
#: différente : la note de débit rectifie une facture tout en portant son
#: montant au crédit, puisqu'elle augmente ce que le client doit. Confondre
#: les deux notions rendait la référence optionnelle pour « ND » — un
#: document irrégulier que le schéma accepte sans rien dire.
TYPES_AU_DEBIT = ('NC',)

#: L'ordre du schéma pour un paiement (`PaymentMethod`). Le mécanisme est
#: optionnel, le montant et la date ne le sont pas.
ORDRE_PAIEMENT = ('PaymentMechanism', 'PaymentAmount', 'PaymentDate')

#: LE MÊME TYPE, SOUS DEUX NOMS D'ÉLÉMENT DIFFÉRENTS.
#:
#: Le type `PaymentMethod` du schéma est employé deux fois, et le nom de
#: l'élément change selon la table :
#:
#:   table 4.1, dans `DocumentTotals` → élément « Payment »
#:   table 4.4, au niveau du reçu     → élément « PaymentMethod »
#:
#: C'est le NOM DE L'ÉLÉMENT qui paraît dans le fichier, pas celui du
#: type. Composer un reçu avec « Payment », par analogie avec la facture,
#: donne un élément inconnu à cet endroit du schéma — et fait refuser le
#: fichier entier pour un nom.
ELEMENT_PAIEMENT_DE_FACTURE = 'Payment'
ELEMENT_PAIEMENT_DE_RECU = 'PaymentMethod'

#: Les états dont les documents sont EXCLUS des sommes de contrôle d'une
#: table, alors qu'ils sont COMPTÉS dans `NumberOfEntries`.
#:
#: Portaria n.º 302/2016, champs 4.1.1 à 4.1.3 : `NumberOfEntries` « deve
#: conter o número total de documentos, incluindo os documentos cujo valor
#: do campo Estado atual (InvoiceStatus) seja do tipo "A" ou "F" », tandis
#: que `TotalDebit` et `TotalCredit` contiennent la somme de contrôle
#: « dela excluindo os documentos em que o campo Estado atual do documento
#: (InvoiceStatus) seja do tipo "A" ou "F" ».
#:
#: Les deux règles sont opposées sur les MÊMES documents, et c'est voulu :
#: un document annulé reste dans le fichier pour prouver qu'aucun numéro
#: ne manque dans la série, mais son montant ne compte plus.
ETATS_HORS_TOTAUX = ('A', 'F')

#: Pour les reçus, champs 4.4.1 à 4.4.3 de la même Portaria : seul « A »
#: existe, parce que `PaymentStatus` n'énumère que « N » et « A ». Reprendre
#: la liste des documents de facturation reviendrait à exclure un état qui
#: ne peut pas se produire — inoffensif aujourd'hui, faux à relire.
ETATS_DE_RECU_HORS_TOTAUX = ('A',)

ORDRE_ETAT_DE_RECU = ('PaymentStatus', 'PaymentStatusDate', 'Reason',
                      'SourceID', 'SourcePayment')

ORDRE_DOCUMENT_SOURCE = ('OriginatingON', 'InvoiceDate', 'Description')

ORDRE_LIGNE_DE_RECU = ('LineNumber', 'SourceDocumentID', 'SettlementAmount',
                       'DebitAmount', 'CreditAmount', 'Tax',
                       'TaxExemptionReason', 'TaxExemptionCode')

#: L'ordre des totaux D'UN REÇU, et il n'est PAS celui d'une facture.
#:
#: Table 4.1 : TaxPayable, NetTotal, GrossTotal, Currency, Settlement, Payment
#: Table 4.4 : TaxPayable, NetTotal, GrossTotal, Settlement, Currency
#:
#: `Currency` et `Settlement` sont INVERSÉS entre les deux tables. Rien ne
#: le justifie et le schéma ne s'en explique pas ; il faut l'avoir relevé.
#: Réemployer `ORDRE_TOTAUX` pour un reçu paraît évident, produit un
#: fichier dont seul l'ordre de deux éléments optionnels diffère, et le
#: fait refuser en entier.
ORDRE_TOTAUX_DE_RECU = ('TaxPayable', 'NetTotal', 'GrossTotal', 'Settlement',
                        'Currency')

ORDRE_RECU = ('PaymentRefNo', 'ATCUD', 'Period', 'TransactionID',
              'TransactionDate', 'PaymentType', 'Description', 'SystemID',
              'DocumentStatus', 'PaymentMethod', 'SourceID',
              'SystemEntryDate', 'CustomerID', 'Line', 'DocumentTotals',
              'WithholdingTax')


class ErreurSAFT(Exception):
    """Ce qui a empêché l'export, dit dans des termes exploitables."""


# ── Mise en forme ────────────────────────────────────────────────────────────

def _montant(valeur):
    """Deux décimales, point décimal. Le schéma est un `decimal` ; le
    validateur de l'AT, lui, compare les totaux au centime."""
    return str(Decimal(str(valeur or 0)).quantize(Decimal('0.01'),
                                                  rounding=ROUND_HALF_UP))


def _quantite(valeur):
    """Jusqu'à cinq décimales, sans zéros inutiles à droite."""
    nombre = Decimal(str(valeur or 0)).quantize(Decimal('0.00001'),
                                                rounding=ROUND_HALF_UP)
    texte = format(nombre.normalize(), 'f')
    return texte if '.' not in texte or texte[-1] != '.' else texte[:-1]


def _date(valeur):
    return str(valeur)[:10]


def _horodatage(valeur):
    """AAAA-MM-JJTHH:MM:SS, sans fuseau — comme dans la chaîne signée."""
    texte = str(valeur).replace(' ', 'T')[:19]
    return texte


def _ajouter(parent, ordre, valeurs):
    """Ajoute des sous-éléments DANS L'ORDRE DU SCHÉMA.

    `valeurs` est un dictionnaire ; on parcourt `ordre`, pas le
    dictionnaire. C'est le cœur du module : l'ordre d'insertion dans un
    dictionnaire Python est celui de l'écriture du code, et il finirait
    par diverger du schéma au premier champ ajouté au mauvais endroit.

    Les valeurs absentes ou vides sont omises — un élément optionnel vide
    n'est pas « rien » pour un validateur XSD : c'est une chaîne vide, qui
    viole le plus souvent la longueur minimale.
    """
    for nom in ordre:
        if nom not in valeurs:
            continue
        valeur = valeurs[nom]
        if valeur is None or valeur == '':
            continue
        if isinstance(valeur, ET.Element):
            parent.append(valeur)
        elif isinstance(valeur, (list, tuple)):
            for element in valeur:
                parent.append(element)
        else:
            ET.SubElement(parent, nom).text = str(valeur)
    return parent


def _exiger(valeurs, champs, contexte):
    manquants = [c for c in champs if not str(valeurs.get(c) or '').strip()]
    if manquants:
        raise ErreurSAFT(
            f'{contexte} : champ(s) obligatoire(s) absent(s) — '
            f'{", ".join(manquants)}. Le validateur de l’AT rejette le '
            'fichier entier, et son message désigne l’élément suivant, pas '
            'celui qui manque.')


# ── Les blocs ────────────────────────────────────────────────────────────────

def _adresse(nom_element, donnees):
    element = ET.Element(nom_element)
    _ajouter(element, ORDRE_ADRESSE, {
        'BuildingNumber': donnees.get('numero'),
        'StreetName': donnees.get('rue'),
        'AddressDetail': donnees.get('adresse') or donnees.get('rue') or '',
        'City': donnees.get('ville') or '',
        'PostalCode': donnees.get('code_postal') or '',
        'Region': donnees.get('region'),
        'Country': donnees.get('pays') or 'PT',
    })
    return element


def entete(donnees):
    """Le bloc `Header`.

    `SoftwareCertificateNumber` vaut 0 tant que l'AT n'a pas attribué de
    numéro. C'est la valeur prévue par le schéma pour un logiciel non
    certifié : y mettre un numéro d'emprunt serait une fausse déclaration,
    et le champ est contrôlé.
    """
    _exiger(donnees, ('nif', 'nom', 'exercice', 'debut', 'fin'), 'En-tête')

    element = ET.Element('Header')
    _ajouter(element, ORDRE_ENTETE, {
        'AuditFileVersion': VERSION,
        'CompanyID': donnees.get('identifiant_societe') or donnees['nif'],
        'TaxRegistrationNumber': donnees['nif'],
        'TaxAccountingBasis': donnees.get('base_comptable', BASE_COMPTABLE),
        'CompanyName': donnees['nom'],
        'BusinessName': donnees.get('enseigne'),
        'CompanyAddress': _adresse('CompanyAddress',
                                   donnees.get('adresse') or {}),
        'FiscalYear': donnees['exercice'],
        'StartDate': _date(donnees['debut']),
        'EndDate': _date(donnees['fin']),
        'CurrencyCode': 'EUR',
        'DateCreated': _date(donnees.get('cree_le') or donnees['fin']),
        'TaxEntity': donnees.get('entite', 'Global'),
        'ProductCompanyTaxID': donnees.get('nif_editeur') or donnees['nif'],
        'SoftwareCertificateNumber': donnees.get('numero_de_certificat', '0'),
        'ProductID': donnees.get('produit', 'Orion ERP/Orion'),
        'ProductVersion': donnees.get('version_produit', '1.0'),
    })
    return element


def client(donnees):
    """Un `Customer` du référentiel.

    `CustomerTaxID` porte « 999999990 » pour le consommateur final : le
    schéma l'exige, et un champ vide serait refusé.
    """
    _exiger(donnees, ('identifiant', 'nom'), 'Client')

    element = ET.Element('Customer')
    _ajouter(element, ORDRE_CLIENT, {
        'CustomerID': donnees['identifiant'],
        'AccountID': donnees.get('compte') or 'Desconhecido',
        'CustomerTaxID': donnees.get('nif') or NIF_CONSOMMATEUR_FINAL,
        'CompanyName': donnees['nom'],
        'BillingAddress': _adresse('BillingAddress',
                                   donnees.get('adresse') or {}),
        'Telephone': donnees.get('telephone'),
        'Email': donnees.get('courriel'),
        'SelfBillingIndicator': donnees.get('autofacturation', '0'),
    })
    return element


def produit(donnees):
    """Un `Product` du référentiel.

    Chaque `ProductCode` employé sur une ligne doit se retrouver ici. Le
    validateur le vérifie, et c'est l'oubli le plus fréquent : les lignes
    sont justes, le référentiel est incomplet, et le fichier est rejeté.
    """
    _exiger(donnees, ('code', 'description'), 'Produit')

    element = ET.Element('Product')
    _ajouter(element, ORDRE_PRODUIT, {
        'ProductType': donnees.get('type', 'S'),  # S = service
        'ProductCode': donnees['code'],
        'ProductGroup': donnees.get('groupe'),
        'ProductDescription': donnees['description'][:200],
        'ProductNumberCode': donnees.get('code_barres') or donnees['code'],
    })
    return element


def entree_de_taux(code, pourcentage, region='PT'):
    """Une `TaxTableEntry`."""
    element = ET.Element('TaxTableEntry')
    _ajouter(element, ORDRE_TAUX, {
        'TaxType': 'IVA',
        'TaxCountryRegion': region,
        'TaxCode': code,
        'Description': LIBELLES_DE_TAUX.get(code, code),
        'TaxPercentage': _montant(pourcentage),
    })
    return element


def references(document_rectifie, motif):
    """Le bloc `References` d'une ligne de note de crédit.

    POURQUOI IL EST OBLIGATOIRE ICI

    Une note de crédit qui ne désigne pas le document qu'elle rectifie est
    un avoir dans le vide : l'administration ne peut pas rapprocher les
    deux, et le SAF-T l'exige pour cette raison. Le motif, lui, est ce qui
    distingue un geste commercial d'une erreur de facturation.
    """
    element = ET.Element('References')
    if document_rectifie:
        ET.SubElement(element, 'Reference').text = str(document_rectifie)
    if motif:
        ET.SubElement(element, 'Reason').text = str(motif)[:50]
    return element


def ligne(numero, donnees, type_document='FT'):
    """Une `Line` de document.

    Le montant va au CRÉDIT pour une facture et au DÉBIT pour une note de
    crédit. Les inverser donne un fichier qui s'équilibre à l'envers, et
    le validateur l'accepte sans rien dire : seul le contrôle le relève.
    """
    _exiger(donnees, ('code_produit', 'description'), f'Ligne {numero}')

    taxe = ET.Element('Tax')
    _ajouter(taxe, ORDRE_TAXE_DE_LIGNE, {
        'TaxType': 'IVA',
        'TaxCountryRegion': donnees.get('region', 'PT'),
        'TaxCode': donnees.get('code_de_taux', 'NOR'),
        'TaxPercentage': _montant(donnees.get('taux', 0)),
    })

    champ_montant = ('DebitAmount' if type_document in TYPES_AU_DEBIT
                     else 'CreditAmount')

    element = ET.Element('Line')
    valeurs = {
        'LineNumber': numero,
        'ProductCode': donnees['code_produit'],
        'ProductDescription': str(donnees['description'])[:200],
        'Quantity': _quantite(donnees.get('quantite', 1)),
        'UnitOfMeasure': donnees.get('unite') or 'UN',
        'UnitPrice': _montant(donnees.get('prix_unitaire', 0)),
        'TaxPointDate': _date(donnees['date']),
        'Description': str(donnees['description'])[:200],
        champ_montant: _montant(donnees.get('montant', 0)),
        'Tax': taxe,
    }

    # Un document RECTIFICATIF — avoir comme note de débit — doit désigner
    # la facture qu'il corrige.
    #
    # Sans cette référence, l'administration ne peut pas rapprocher les
    # deux : le fichier est valide au schéma et le document reste
    # orphelin, ce qui est exactement ce qu'un contrôle cherche. La liste
    # employée ici est celle des rectificatifs, PAS celle du sens
    # débit/crédit : la note de débit rectifie et va au crédit.
    if tipos.exige_une_rectification(type_document):
        rectifie = donnees.get('document_rectifie')
        if not rectifie:
            raise ErreurSAFT(
                f'Ligne {numero} : un document de type « {type_document} » '
                'doit désigner la facture qu’il rectifie. Sans cette '
                'référence le document reste orphelin dans le fichier, et le '
                'contrôle le relève ; le schéma, lui, l’accepte.')
        valeurs['References'] = references(rectifie,
                                           donnees.get('motif_rectification'))
    elif donnees.get('document_rectifie'):
        valeurs['References'] = references(
            donnees['document_rectifie'],
            donnees.get('motif_rectification'))

    # Une ligne exonérée DOIT porter son motif d'exonération. C'est une
    # obligation du schéma, et la facture, elle, n'a l'air de rien manquer.
    if donnees.get('code_de_taux') == 'ISE':
        motif = donnees.get('motif_exoneration')
        code = donnees.get('code_exoneration')
        if not motif or not code:
            raise ErreurSAFT(
                f'Ligne {numero} : une ligne exonérée doit porter son motif '
                'd’exonération et son code (ex. « M07 »). Le schéma les '
                'exige dès que le code de taux vaut ISE.')
        valeurs['TaxExemptionReason'] = motif
        valeurs['TaxExemptionCode'] = code

    _ajouter(element, ORDRE_LIGNE, valeurs)
    return element


def paiement(donnees, nom=ELEMENT_PAIEMENT_DE_FACTURE):
    """Un moyen de paiement — ce qu'une facture-reçu ou un reçu atteste.

    Le schéma nomme le TYPE « PaymentMethod » et l'ÉLÉMENT « Payment »
    dans `DocumentTotals` d'une facture, « PaymentMethod » au niveau d'un
    reçu. Les trois noms désignent la même structure ; c'est le nom de
    l'élément qui doit paraître dans le fichier, et il dépend de la table.
    `nom` le porte donc, plutôt que d'être écrit en dur.

    `PaymentMechanism` est optionnel au schéma, mais une quittance qui ne
    dit pas comment la somme a été reçue ne prouve pas grand-chose : on le
    réclame ici, et on refuse un code hors énumération plutôt que de
    laisser l'AT rejeter le fichier entier sans nommer le document fautif.
    """
    mecanisme = donnees.get('mecanisme')
    try:
        tipos.valider_le_mecanisme(mecanisme)
    except tipos.RegleDeType as exc:
        raise ErreurSAFT(str(exc))

    if donnees.get('montant') is None:
        raise ErreurSAFT(
            'Un paiement sans montant ne peut pas être exporté : '
            '« PaymentAmount » est obligatoire au schéma.')
    if not donnees.get('date'):
        raise ErreurSAFT(
            'Un paiement sans date ne peut pas être exporté : '
            '« PaymentDate » est obligatoire au schéma.')

    element = ET.Element(nom)
    _ajouter(element, ORDRE_PAIEMENT, {
        'PaymentMechanism': mecanisme,
        'PaymentAmount': _montant(donnees['montant']),
        'PaymentDate': _date(donnees['date']),
    })
    return element


# ── Les reçus (table 4.4) ────────────────────────────────────────────────────

def document_source(donnees):
    """Le `SourceDocumentID` d'une ligne de reçu : ce que le reçu solde.

    Le numéro ET la date du document réglé. La date n'est pas une
    redondance : elle permet à l'administration de rapprocher les deux
    tables sans supposer que la numérotation soit chronologique.
    """
    _exiger(donnees, ('document', 'date'), 'Affectation d’un reçu')

    element = ET.Element('SourceDocumentID')
    _ajouter(element, ORDRE_DOCUMENT_SOURCE, {
        'OriginatingON': str(donnees['document'])[:60],
        'InvoiceDate': _date(donnees['date']),
        'Description': (str(donnees.get('description'))[:200]
                        if donnees.get('description') else None),
    })
    return element


def ligne_de_recu(numero, donnees):
    """Une `Line` de reçu, qui n'a rien de commun avec une ligne de facture.

    Pas de produit, pas de quantité, pas de prix unitaire : une ligne de
    reçu affecte une somme à un document. Le schéma définit d'ailleurs
    quatre `Line` différents, et celui des reçus n'a même pas de
    `ProductCode`.

    Le montant va au DÉBIT quand le règlement fait sortir l'argent — le
    remboursement d'un avoir — et au CRÉDIT quand il en fait entrer.
    Aucun bloc `Tax` n'est composé : un reçu « RG » n'indique pas de taux,
    et le schéma ne l'exige que des reçus « RC » du régime de TVA sur les
    encaissements, qui ne sont pas émis ici. Déclarer un `Tax` à zéro
    obligerait en outre à porter un motif d'exonération, qu'un reçu n'a
    pas à inventer.
    """
    champ = 'DebitAmount' if donnees.get('au_debit') else 'CreditAmount'

    element = ET.Element('Line')
    _ajouter(element, ORDRE_LIGNE_DE_RECU, {
        'LineNumber': numero,
        'SourceDocumentID': document_source(donnees),
        champ: _montant(donnees.get('montant', 0)),
    })
    return element


def recu(donnees):
    """Un `Payment` de la table 4.4 — un reçu émis.

    CE QU'IL NE PORTE PAS, ET POURQUOI CE N'EST PAS UN OUBLI

    Ni `Hash` ni `HashControl` : la table 4.4 n'a pas ces champs. Le
    Despacho 8632/2014 (1.1) exclut expressément les reçus de l'obligation
    de signature — « devem assinar quaisquer documentos emitidos com
    eficácia externa, com exceção dos recibos ». Le schéma et le texte
    disent donc la même chose, chacun à sa manière.

    `ATCUD`, en revanche, est OBLIGATOIRE ici — le schéma le rend
    `minOccurs` par défaut, c'est-à-dire exigé. Un reçu se numérote donc
    dans une série déclarée à l'AT, exactement comme une facture.
    """
    _exiger(donnees, ('numero', 'atcud', 'date', 'type', 'horodatage',
                      'client'),
            f'Reçu {donnees.get("numero", "?")}')

    etat = ET.Element('DocumentStatus')
    _ajouter(etat, ORDRE_ETAT_DE_RECU, {
        'PaymentStatus': donnees.get('etat', 'N'),
        'PaymentStatusDate': _horodatage(donnees['horodatage']),
        'Reason': donnees.get('motif'),
        'SourceID': donnees.get('operateur') or 'Orion',
        'SourcePayment': donnees.get('origine', 'P'),  # P = produit ici
    })

    affectations = donnees.get('affectations') or []
    if not affectations:
        raise ErreurSAFT(
            f'Le reçu {donnees["numero"]} n’affecte aucune somme à aucun '
            'document. Le schéma exige au moins une ligne, et chaque ligne '
            'doit nommer le document réglé : un reçu orphelin ne solde rien '
            'que l’administration puisse rapprocher.')

    encaissements = donnees.get('paiements') or []
    if not encaissements:
        raise ErreurSAFT(
            f'Le reçu {donnees["numero"]} ne dit pas comment la somme a été '
            'reçue. Le schéma rend « PaymentMethod » optionnel ; un reçu '
            'qui ne porte aucun moyen de paiement n’atteste pourtant rien '
            'de vérifiable.')

    totaux = ET.Element('DocumentTotals')
    _ajouter(totaux, ORDRE_TOTAUX_DE_RECU, {
        'TaxPayable': _montant(donnees.get('total_taxes', 0)),
        'NetTotal': _montant(donnees.get('total_base', 0)),
        'GrossTotal': _montant(donnees.get('total', 0)),
    })

    periode = donnees.get('periode') or int(_date(donnees['date'])[5:7])

    element = ET.Element('Payment')
    _ajouter(element, ORDRE_RECU, {
        'PaymentRefNo': donnees['numero'],
        'ATCUD': donnees['atcud'],
        'Period': periode,
        'TransactionDate': _date(donnees['date']),
        'PaymentType': donnees['type'],
        'Description': donnees.get('description'),
        'DocumentStatus': etat,
        'PaymentMethod': [paiement(contenu, ELEMENT_PAIEMENT_DE_RECU)
                          for contenu in encaissements],
        'SourceID': donnees.get('operateur') or 'Orion',
        'SystemEntryDate': _horodatage(donnees['horodatage']),
        'CustomerID': donnees['client'],
        'Line': [ligne_de_recu(rang, contenu)
                 for rang, contenu in enumerate(affectations, start=1)],
        'DocumentTotals': totaux,
    })
    return element


def document(donnees):
    """Un `Invoice` complet.

    `Hash` porte la signature de 172 caractères, et `HashControl` la
    VERSION DE LA CLÉ qui l'a produite — pas un contrôle du hachage, en
    dépit du nom.
    """
    _exiger(donnees, ('numero', 'atcud', 'signature', 'version_cle',
                      'date', 'type', 'horodatage', 'client'),
            f'Document {donnees.get("numero", "?")}')

    etat = ET.Element('DocumentStatus')
    _ajouter(etat, ORDRE_ETAT, {
        'InvoiceStatus': donnees.get('etat', 'N'),
        'InvoiceStatusDate': _horodatage(donnees['horodatage']),
        'Reason': donnees.get('motif'),
        'SourceID': donnees.get('operateur') or 'Orion',
        'SourceBilling': donnees.get('origine', 'P'),  # P = produit ici
    })

    regimes = ET.Element('SpecialRegimes')
    _ajouter(regimes, ORDRE_REGIMES, {
        'SelfBillingIndicator': donnees.get('autofacturation', '0'),
        'CashVATSchemeIndicator': donnees.get('tva_sur_encaissement', '0'),
        'ThirdPartiesBillingIndicator': donnees.get('facture_par_tiers', '0'),
    })

    lignes = donnees.get('lignes') or []
    if not lignes:
        raise ErreurSAFT(
            f'Le document {donnees["numero"]} n’a aucune ligne. Le schéma en '
            'exige au moins une ; un document sans ligne fait rejeter le '
            'fichier entier.')

    elements_de_ligne = [ligne(rang, contenu, donnees['type'])
                         for rang, contenu in enumerate(lignes, start=1)]

    # « Payment » vient APRÈS « Currency » et « Settlement » dans la
    # séquence : il est rangé par `ORDRE_TOTAUX`, et non ajouté à la fin.
    totaux = ET.Element('DocumentTotals')
    _ajouter(totaux, ORDRE_TOTAUX, {
        'TaxPayable': _montant(donnees.get('total_taxes', 0)),
        'NetTotal': _montant(donnees.get('total_base', 0)),
        'GrossTotal': _montant(donnees.get('total', 0)),
        'Payment': [paiement(contenu)
                    for contenu in (donnees.get('paiements') or [])],
    })

    # La période est le MOIS du document. Une période fausse ne casse pas
    # le schéma : elle range le document dans le mauvais mois, et l'écart
    # n'apparaît qu'au rapprochement des déclarations.
    periode = donnees.get('periode') or int(_date(donnees['date'])[5:7])

    element = ET.Element('Invoice')
    _ajouter(element, ORDRE_DOCUMENT, {
        'InvoiceNo': donnees['numero'],
        'ATCUD': donnees['atcud'],
        'DocumentStatus': etat,
        'Hash': donnees['signature'],
        'HashControl': str(donnees['version_cle']),
        'Period': periode,
        'InvoiceDate': _date(donnees['date']),
        'InvoiceType': donnees['type'],
        'SpecialRegimes': regimes,
        'SourceID': donnees.get('operateur') or 'Orion',
        'SystemEntryDate': _horodatage(donnees['horodatage']),
        'CustomerID': donnees['client'],
        'Line': elements_de_ligne,
        'DocumentTotals': totaux,
    })
    return element


def _sommes_de_controle(enregistrements, champ_etat_exclu, montants):
    """Les deux sommes de contrôle d'une table, et ce qu'elles excluent.

    LA RÈGLE, ET POURQUOI ELLE EST CONTRE-INTUITIVE

    Portaria n.º 302/2016, champs 4.1.1 à 4.1.3 et 4.4.1 à 4.4.3 :
    `NumberOfEntries` compte TOUS les documents, « incluindo os
    documentos cujo valor do campo Estado atual seja do tipo "A" ou "F" » ;
    `TotalDebit` et `TotalCredit` somment les montants de lignes « dela
    excluindo » ces mêmes documents.

    Deux règles opposées sur les mêmes documents, donc, et chacune pour sa
    raison : un document annulé reste dans le fichier pour prouver que la
    série ne saute aucun numéro, mais son montant ne compte plus nulle
    part.

    LE DÉFAUT QUE CETTE FONCTION FERME

    Les totaux étaient calculés sur TOUS les documents, sans regarder leur
    état. Un seul document annulé dans la période gonflait donc
    `TotalCredit` de son montant, et le validateur de l'AT — qui recompte —
    refusait le fichier entier.

    Le pire n'était pas là : notre propre contrôle de cohérence appliquait
    la MÊME règle fausse, donc il confirmait le fichier. Un défaut qu'on
    vérifie avec la méthode qui l'a produit n'apparaît jamais. Aucun
    document n'est annulé aujourd'hui — rien dans le logiciel ne le
    permet —, ce qui rend le défaut latent plutôt que visible : il
    attendait la première annulation.

    `montants` rend, pour un enregistrement, la liste (montant, au_debit)
    de ses lignes. On somme les LIGNES et non le total du document, parce
    que c'est ce que le texte nomme : « a soma de controlo do campo Valor
    a crédito (CreditAmount) ».
    """
    debit = Decimal('0')
    credit = Decimal('0')

    for enregistrement in enregistrements:
        if enregistrement.get('etat') in champ_etat_exclu:
            continue
        for montant, au_debit in montants(enregistrement):
            if au_debit:
                debit += Decimal(str(montant or 0))
            else:
                credit += Decimal(str(montant or 0))

    return debit, credit


def _montants_d_un_document(donnees):
    """Les montants de lignes d'une facture, et leur sens.

    Le sens est celui du DOCUMENT : toutes les lignes d'un avoir vont au
    débit, toutes celles d'une facture au crédit.
    """
    au_debit = donnees.get('type') in TYPES_AU_DEBIT
    return [(ligne.get('montant', 0), au_debit)
            for ligne in (donnees.get('lignes') or [])]


def _montants_d_un_recu(donnees):
    """Les montants d'affectation d'un reçu, et leur sens.

    Le sens est porté par CHAQUE LIGNE et non par le reçu : c'est le
    document réglé qui décide si l'argent entre ou sort. `tipos` refuse
    d'ailleurs un reçu qui mêlerait les deux.
    """
    return [(ligne.get('montant', 0), bool(ligne.get('au_debit')))
            for ligne in (donnees.get('affectations') or [])]


def composer(donnees_entete, clients, produits, taux, documents, recus=()):
    """Le fichier complet, en octets prêts à écrire.

    Les totaux de chaque table sont RECALCULÉS ici depuis les documents,
    jamais repris d'un cumul tenu ailleurs. Le validateur de l'AT les
    recompte : un cumul entretenu à côté finirait par dériver d'un centime,
    et l'export serait refusé sans qu'on sache pourquoi.

    `recus` alimente la table 4.4 `Payments`. Elle est OMISE quand il n'y
    a aucun reçu dans la période — le schéma la rend optionnelle, et une
    table annoncée à zéro enregistrement se lirait comme une déclaration
    là où il n'y a rien à déclarer.
    """
    racine = ET.Element('AuditFile', {'xmlns': ESPACE_DE_NOMS})
    racine.append(entete(donnees_entete))

    referentiels = ET.SubElement(racine, 'MasterFiles')
    for donnees in clients:
        referentiels.append(client(donnees))
    for donnees in produits:
        referentiels.append(produit(donnees))

    table = ET.SubElement(referentiels, 'TaxTable')
    for code, pourcentage, region in taux:
        table.append(entree_de_taux(code, pourcentage, region))

    sources = ET.SubElement(racine, 'SourceDocuments')

    # `SalesInvoices` d'abord, `Payments` en dernier : c'est l'ordre de la
    # séquence `SourceDocuments`, où s'intercalent MovementOfGoods et
    # WorkingDocuments, que ce module ne produit pas.
    documents = list(documents)
    ventes = ET.SubElement(sources, 'SalesInvoices')
    debit, credit = _sommes_de_controle(documents, ETATS_HORS_TOTAUX,
                                        _montants_d_un_document)

    # NumberOfEntries, TotalDebit et TotalCredit précèdent les documents :
    # l'ordre du schéma, encore une fois.
    ET.SubElement(ventes, 'NumberOfEntries').text = str(len(documents))
    ET.SubElement(ventes, 'TotalDebit').text = _montant(debit)
    ET.SubElement(ventes, 'TotalCredit').text = _montant(credit)
    for donnees in documents:
        ventes.append(document(donnees))

    recus = list(recus or [])
    if recus:
        table_des_recus = ET.SubElement(sources, 'Payments')
        debit, credit = _sommes_de_controle(recus, ETATS_DE_RECU_HORS_TOTAUX,
                                            _montants_d_un_recu)
        ET.SubElement(table_des_recus, 'NumberOfEntries').text = str(
            len(recus))
        ET.SubElement(table_des_recus, 'TotalDebit').text = _montant(debit)
        ET.SubElement(table_des_recus, 'TotalCredit').text = _montant(credit)
        for donnees in recus:
            table_des_recus.append(recu(donnees))

    ET.indent(racine, space='  ')
    return (b'<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(racine, encoding='utf-8'))
