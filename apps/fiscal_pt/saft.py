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
facturation.
"""

from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree as ET

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

#: L'ordre des éléments, tel que le schéma les énumère. Chaque liste se
#: relit directement contre le XSD — c'est là tout l'intérêt de les
#: écrire plutôt que de les coder en dur dans la construction.
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
                 'ProductDescription', 'ProductNumberCode')

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
                  'DocumentTotals')

ORDRE_LIGNE = ('LineNumber', 'OrderReferences', 'ProductCode',
               'ProductDescription', 'Quantity', 'UnitOfMeasure', 'UnitPrice',
               'TaxBase', 'TaxPointDate', 'References', 'Description',
               'ProductSerialNumber', 'DebitAmount', 'CreditAmount', 'Tax',
               'TaxExemptionReason', 'TaxExemptionCode', 'SettlementAmount')

ORDRE_TAXE_DE_LIGNE = ('TaxType', 'TaxCountryRegion', 'TaxCode',
                       'TaxPercentage', 'TaxAmount')

ORDRE_TOTAUX = ('TaxPayable', 'NetTotal', 'GrossTotal', 'Currency',
                'Settlement', 'Payment')

#: Les types de documents qui portent un montant au DÉBIT et non au crédit.
#: Une note de crédit inversée dans les totaux fait un fichier qui s'équilibre
#: à l'envers, et le validateur ne le dit pas : il accepte.
TYPES_AU_DEBIT = ('NC',)


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

    totaux = ET.Element('DocumentTotals')
    _ajouter(totaux, ORDRE_TOTAUX, {
        'TaxPayable': _montant(donnees.get('total_taxes', 0)),
        'NetTotal': _montant(donnees.get('total_base', 0)),
        'GrossTotal': _montant(donnees.get('total', 0)),
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


def composer(donnees_entete, clients, produits, taux, documents):
    """Le fichier complet, en octets prêts à écrire.

    Les totaux de `SalesInvoices` sont RECALCULÉS ici depuis les documents,
    jamais repris d'un cumul tenu ailleurs. Le validateur de l'AT les
    recompte : un cumul entretenu à côté finirait par dériver d'un centime,
    et l'export serait refusé sans qu'on sache pourquoi.
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
    ventes = ET.SubElement(sources, 'SalesInvoices')

    credit = Decimal('0')
    debit = Decimal('0')
    elements = []
    for donnees in documents:
        elements.append(document(donnees))
        base = Decimal(str(donnees.get('total_base') or 0))
        if donnees.get('type') in TYPES_AU_DEBIT:
            debit += base
        else:
            credit += base

    # NumberOfEntries, TotalDebit et TotalCredit précèdent les documents :
    # l'ordre du schéma, encore une fois.
    ET.SubElement(ventes, 'NumberOfEntries').text = str(len(elements))
    ET.SubElement(ventes, 'TotalDebit').text = _montant(debit)
    ET.SubElement(ventes, 'TotalCredit').text = _montant(credit)
    for element in elements:
        ventes.append(element)

    ET.indent(racine, space='  ')
    return (b'<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(racine, encoding='utf-8'))
