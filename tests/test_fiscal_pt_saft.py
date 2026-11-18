"""L'export SAF-T (PT) : l'ordre, les totaux, et ce que le schéma exige.

POURQUOI CES TESTS PORTENT SURTOUT SUR L'ORDRE

Le schéma de l'AT décrit chaque bloc comme une séquence. Un élément
déplacé fait rejeter le fichier ENTIER, et le message du validateur
désigne l'élément SUIVANT, pas celui qui manque — on cherche alors le
défaut au mauvais endroit. Ces tests figent donc l'ordre attendu, bloc
par bloc, pour qu'un champ ajouté plus tard au mauvais endroit se voie
ici et non six mois après, à la première remise du fichier.
"""
from datetime import date, datetime
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest

from apps.fiscal_pt import saft


ENTETE = {
    'nif': '123456789',
    'nom': 'Orion Lusitana Lda',
    'exercice': '2026',
    'debut': date(2026, 1, 1),
    'fin': date(2026, 12, 31),
    'adresse': {'adresse': 'Rua do Comércio 1', 'ville': 'Lisboa',
                'code_postal': '1100-150', 'pays': 'PT'},
    'numero_de_certificat': '0',
}

CLIENTS = [{'identifiant': 'C1', 'nom': 'Cliente Lda', 'nif': '500000000',
            'adresse': {'adresse': 'Av. da Liberdade 2', 'ville': 'Lisboa',
                        'code_postal': '1250-096'}}]

PRODUITS = [{'code': 'P1', 'description': 'Prestação de serviços'}]

TAUX = [('NOR', Decimal('23'), 'PT'), ('RED', Decimal('6'), 'PT')]

LIGNE = {'code_produit': 'P1', 'description': 'Prestação de serviços',
         'quantite': 1, 'prix_unitaire': Decimal('100.00'),
         'date': date(2026, 3, 7), 'montant': Decimal('100.00'),
         'taux': Decimal('23'), 'code_de_taux': 'NOR'}

DOCUMENT = {
    'numero': 'FT A/1', 'atcud': 'CSDF7T5H-1',
    'signature': 'S' * 172, 'version_cle': 1,
    'date': date(2026, 3, 7), 'type': 'FT',
    'horodatage': datetime(2026, 3, 7, 10, 30, 0),
    'client': 'C1', 'lignes': [LIGNE],
    'total_base': Decimal('100.00'), 'total_taxes': Decimal('23.00'),
    'total': Decimal('123.00'),
}


def _fichier(documents=None):
    return saft.composer(ENTETE, CLIENTS, PRODUITS, TAUX,
                         documents if documents is not None else [DOCUMENT])


def _racine(documents=None):
    return ET.fromstring(_fichier(documents))


def _noms(element):
    """Les noms des enfants, sans l'espace de noms."""
    return [enfant.tag.split('}')[-1] for enfant in element]


def _trouver(racine, chemin):
    espace = f'{{{saft.ESPACE_DE_NOMS}}}'
    return racine.find('/'.join(espace + p for p in chemin.split('/')))


# ── Le fichier dans son ensemble ─────────────────────────────────────────────

def test_le_fichier_est_un_xml_valide_et_declare_l_espace_de_noms():
    octets = _fichier()

    assert octets.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    assert saft.ESPACE_DE_NOMS.encode() in octets
    ET.fromstring(octets)  # ne lève pas


def test_les_trois_blocs_sont_dans_l_ordre():
    assert _noms(_racine()) == ['Header', 'MasterFiles', 'SourceDocuments']


def test_la_version_annoncee_est_celle_de_la_facturation():
    assert _trouver(_racine(), 'Header/AuditFileVersion').text == '1.04_01'


# ── L'ordre, bloc par bloc ───────────────────────────────────────────────────

def test_l_entete_suit_l_ordre_du_schema():
    assert _noms(_trouver(_racine(), 'Header')) == [
        'AuditFileVersion', 'CompanyID', 'TaxRegistrationNumber',
        'TaxAccountingBasis', 'CompanyName', 'CompanyAddress', 'FiscalYear',
        'StartDate', 'EndDate', 'CurrencyCode', 'DateCreated', 'TaxEntity',
        'ProductCompanyTaxID', 'SoftwareCertificateNumber', 'ProductID',
        'ProductVersion']


def test_l_adresse_suit_l_ordre_du_schema():
    """« City » avant « PostalCode », et « Country » en dernier. L’ordre
    intuitif — code postal puis ville, comme sur une enveloppe — est
    précisément l’inverse."""
    assert _noms(_trouver(_racine(), 'Header/CompanyAddress')) == [
        'AddressDetail', 'City', 'PostalCode', 'Country']


def test_le_document_suit_l_ordre_du_schema():
    """L’ordre complet d’un `Invoice`. C’est le bloc le plus long et celui
    où un champ s’ajoute le plus facilement au mauvais endroit."""
    assert _noms(_trouver(_racine(), 'SourceDocuments/SalesInvoices/Invoice')) == [
        'InvoiceNo', 'ATCUD', 'DocumentStatus', 'Hash', 'HashControl',
        'Period', 'InvoiceDate', 'InvoiceType', 'SpecialRegimes', 'SourceID',
        'SystemEntryDate', 'CustomerID', 'Line', 'DocumentTotals']


def test_la_ligne_suit_l_ordre_du_schema():
    assert _noms(_trouver(
        _racine(), 'SourceDocuments/SalesInvoices/Invoice/Line')) == [
        'LineNumber', 'ProductCode', 'ProductDescription', 'Quantity',
        'UnitOfMeasure', 'UnitPrice', 'TaxPointDate', 'Description',
        'CreditAmount', 'Tax']


def test_les_totaux_de_ventes_precedent_les_documents():
    """NumberOfEntries, TotalDebit et TotalCredit AVANT les `Invoice`.
    Les mettre après paraît plus naturel — on compte ce qu’on a écrit —
    et c’est faux."""
    assert _noms(_trouver(_racine(), 'SourceDocuments/SalesInvoices')) == [
        'NumberOfEntries', 'TotalDebit', 'TotalCredit', 'Invoice']


# ── La signature et l'ATCUD ──────────────────────────────────────────────────

def test_hash_porte_la_signature_et_hashcontrol_la_version_de_cle():
    """« HashControl » ne contrôle pas le hachage, en dépit de son nom :
    il porte la VERSION DE LA CLÉ privée. L’erreur est facile, et le
    fichier reste valide au schéma — l’administration, elle, ne retrouve
    plus la clé publique."""
    racine = _racine()
    base = 'SourceDocuments/SalesInvoices/Invoice'

    assert len(_trouver(racine, f'{base}/Hash').text) == 172
    assert _trouver(racine, f'{base}/HashControl').text == '1'
    assert _trouver(racine, f'{base}/ATCUD').text == 'CSDF7T5H-1'


def test_le_numero_de_certificat_reste_a_zero_sans_certification():
    """Y inscrire un numéro d’emprunt serait une fausse déclaration, et le
    champ est contrôlé."""
    assert _trouver(_racine(),
                    'Header/SoftwareCertificateNumber').text == '0'


# ── Les totaux, recalculés ───────────────────────────────────────────────────

def test_les_totaux_sont_recalcules_depuis_les_documents():
    """Le validateur de l’AT les recompte. Un cumul entretenu à côté
    finirait par dériver d’un centime, et l’export serait refusé sans
    qu’on sache pourquoi."""
    trois = [dict(DOCUMENT, numero=f'FT A/{n}') for n in (1, 2, 3)]
    ventes = _trouver(_racine(trois), 'SourceDocuments/SalesInvoices')

    assert _noms(ventes).count('Invoice') == 3
    assert ventes.find(f'{{{saft.ESPACE_DE_NOMS}}}NumberOfEntries').text == '3'
    assert ventes.find(f'{{{saft.ESPACE_DE_NOMS}}}TotalCredit').text == '300.00'
    assert ventes.find(f'{{{saft.ESPACE_DE_NOMS}}}TotalDebit').text == '0.00'


def test_une_note_de_credit_va_au_debit():
    """Les inverser donne un fichier qui s’équilibre à l’envers, et le
    validateur l’accepte sans rien dire : seul le contrôle le relève."""
    # L'avoir DESIGNE la facture qu'il rectifie : le composer sans cette
    # reference est desormais refuse, et c'est le sujet d'un autre test.
    avoir = dict(DOCUMENT, numero='NC A/1', type='NC',
                 lignes=[dict(LIGNE, document_rectifie='FT A/1',
                              motif_rectification='Devolução')])
    ventes = _trouver(_racine([DOCUMENT, avoir]),
                      'SourceDocuments/SalesInvoices')
    espace = f'{{{saft.ESPACE_DE_NOMS}}}'

    assert ventes.find(f'{espace}TotalCredit').text == '100.00'
    assert ventes.find(f'{espace}TotalDebit').text == '100.00'

    lignes = ventes.findall(f'{espace}Invoice/{espace}Line')
    assert lignes[0].find(f'{espace}CreditAmount') is not None
    assert lignes[1].find(f'{espace}DebitAmount') is not None
    assert lignes[1].find(f'{espace}CreditAmount') is None


def test_les_montants_ont_deux_decimales():
    document = dict(DOCUMENT, total=Decimal('123.5'),
                    total_base=Decimal('100'), total_taxes=Decimal('23.456'))
    totaux = _trouver(_racine([document]),
                      'SourceDocuments/SalesInvoices/Invoice/DocumentTotals')
    espace = f'{{{saft.ESPACE_DE_NOMS}}}'

    assert totaux.find(f'{espace}NetTotal').text == '100.00'
    assert totaux.find(f'{espace}TaxPayable').text == '23.46'
    assert totaux.find(f'{espace}GrossTotal').text == '123.50'


def test_la_periode_est_le_mois_du_document():
    """Une période fausse ne casse pas le schéma : elle range le document
    dans le mauvais mois, et l’écart n’apparaît qu’au rapprochement des
    déclarations."""
    assert _trouver(_racine(),
                    'SourceDocuments/SalesInvoices/Invoice/Period').text == '3'


# ── Ce que le schéma refuse ──────────────────────────────────────────────────

def test_un_document_sans_ligne_est_refuse():
    with pytest.raises(saft.ErreurSAFT, match='aucune ligne'):
        _fichier([dict(DOCUMENT, lignes=[])])


def test_une_ligne_exoneree_doit_porter_son_motif():
    """Obligation du schéma dès que le code de taux vaut ISE — et la
    facture, elle, n’a l’air de rien manquer."""
    exoneree = dict(LIGNE, code_de_taux='ISE', taux=Decimal('0'))

    with pytest.raises(saft.ErreurSAFT, match='exonérée'):
        _fichier([dict(DOCUMENT, lignes=[exoneree])])

    complete = dict(exoneree, motif_exoneration='Artigo 9.º do CIVA',
                    code_exoneration='M07')
    racine = _racine([dict(DOCUMENT, lignes=[complete])])
    ligne = _trouver(racine, 'SourceDocuments/SalesInvoices/Invoice/Line')

    assert _noms(ligne)[-2:] == ['TaxExemptionReason', 'TaxExemptionCode']


def test_un_champ_obligatoire_absent_nomme_le_champ():
    """Le validateur de l’AT, lui, ne le nomme pas — il désigne l’élément
    suivant. Autant le dire ici, où l’information existe encore."""
    with pytest.raises(saft.ErreurSAFT, match='signature'):
        _fichier([dict(DOCUMENT, signature='')])

    with pytest.raises(saft.ErreurSAFT, match='nif'):
        saft.composer(dict(ENTETE, nif=''), CLIENTS, PRODUITS, TAUX,
                      [DOCUMENT])


def test_un_champ_optionnel_vide_est_omis_et_non_ecrit_vide():
    """Un élément optionnel vide n’est pas « rien » pour un validateur
    XSD : c’est une chaîne vide, qui viole la longueur minimale."""
    assert 'BusinessName' not in _noms(_trouver(_racine(), 'Header'))


# ── Le référentiel ───────────────────────────────────────────────────────────

def test_le_consommateur_final_prend_le_nif_conventionnel():
    racine = ET.fromstring(saft.composer(
        ENTETE, [{'identifiant': 'CF', 'nom': 'Consumidor final'}],
        PRODUITS, TAUX, [dict(DOCUMENT, client='CF')]))
    espace = f'{{{saft.ESPACE_DE_NOMS}}}'
    client = racine.find(f'{espace}MasterFiles/{espace}Customer')

    assert client.find(f'{espace}CustomerTaxID').text == '999999990'


def test_le_referentiel_vient_avant_la_table_des_taux():
    assert _noms(_trouver(_racine(), 'MasterFiles')) == [
        'Customer', 'Product', 'TaxTable']


def test_la_table_des_taux_nomme_chaque_palier():
    table = _trouver(_racine(), 'MasterFiles/TaxTable')
    espace = f'{{{saft.ESPACE_DE_NOMS}}}'
    codes = [e.find(f'{espace}TaxCode').text
             for e in table.findall(f'{espace}TaxTableEntry')]

    assert codes == ['NOR', 'RED']
    premiere = table.find(f'{espace}TaxTableEntry')
    assert _noms(premiere) == ['TaxType', 'TaxCountryRegion', 'TaxCode',
                               'Description', 'TaxPercentage']


def test_les_codes_de_taux_couvrent_les_paliers_de_taxas():
    """Les deux modules doivent s’accorder : `taxas` nomme les paliers,
    `saft` les code. Un palier sans code produirait un KeyError à
    l’export, des mois après l’émission des factures."""
    from apps.fiscal_pt import taxas

    paliers = set(taxas.PALIERS_PAR_REGION[taxas.CONTINENT].values())
    assert paliers <= set(saft.CODES_DE_TAUX)


@pytest.mark.parametrize('quantite, attendu', [
    ('1', '1'),
    ('100', '100'),
    ('1000', '1000'),
    ('2.5', '2.5'),
    ('0.001', '0.001'),
])
def test_aucune_quantite_ne_part_en_notation_exponentielle(quantite, attendu):
    """LE PIEGE QUE CE TEST FERME.

    `Decimal('100.00000').normalize()` rend `1E+2`. Ecrit tel quel dans le
    XML, un `<Quantity>1E+2</Quantity>` est invalide, et le validateur de
    l'AT rejette le fichier entier. Seul le `format(..., 'f')` ramene la
    notation decimale -- et il se retire d'un geste en croyant simplifier.
    """
    ligne = dict(LIGNE, quantite=quantite)
    racine = _racine([dict(DOCUMENT, lignes=[ligne])])
    espace = f'{{{saft.ESPACE_DE_NOMS}}}'
    valeur = _trouver(racine,
                      'SourceDocuments/SalesInvoices/Invoice/Line').find(
        f'{espace}Quantity').text

    assert valeur == attendu
    assert 'E' not in valeur.upper()


def test_aucun_montant_ne_part_en_notation_exponentielle():
    """Meme piege sur les montants, ou il couterait davantage : un total
    illisible fait rejeter le fichier, et l'erreur ne se voit pas a la
    lecture du code."""
    document = dict(DOCUMENT, total_base=Decimal('1000'),
                    total_taxes=Decimal('230'), total=Decimal('1230'))
    totaux = _trouver(_racine([document]),
                      'SourceDocuments/SalesInvoices/Invoice/DocumentTotals')
    espace = f'{{{saft.ESPACE_DE_NOMS}}}'

    assert totaux.find(f'{espace}NetTotal').text == '1000.00'
    assert totaux.find(f'{espace}GrossTotal').text == '1230.00'
