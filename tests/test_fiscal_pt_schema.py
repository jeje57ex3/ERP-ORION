"""Le SAF-T produit par l'ERP, contre le schéma publié par l'AT.

CE QUE CE FICHIER APPORTE DE PLUS QUE `test_fiscal_pt_saft.py`

Celui-là fige l'ordre des éléments d'après une LECTURE du schéma.
Celui-ci lit le schéma lui-même — `apps/fiscal_pt/schemas/
SAFTPT1.04_01.xsd`, tel que l'AT le publie — et compare.

La différence compte : une liste recopiée à la main peut être fausse, et
un test écrit d'après la même lecture confirmerait la même erreur.

LES DEUX FAÇONS DONT UN VALIDATEUR ÉCHOUE

Un validateur peut échouer dans les deux sens, et les deux sont graves :

1. **Il ne connaît rien et accepte tout.** C'est arrivé : une première
   version lisait l'attribut `name` des déclarations d'éléments, alors
   que le schéma les référence presque toujours par `ref=`, où `name`
   est absent. Le modèle connaissait DEUX chemins au lieu de
   soixante-dix-huit, et annonçait « structure conforme » sur n'importe
   quoi.

2. **Il crie à tort et finit par être ignoré.** C'est arrivé aussi : les
   branches d'un `choice` étaient comptées chacune obligatoire. Le
   validateur réclamait `DebitAmount` sur une facture et `TaxAmount` à
   côté d'un `TaxPercentage` — quatre anomalies sur un fichier
   parfaitement conforme.

Les tests ci-dessous couvrent donc les deux sens : que le fichier juste
passe, ET que le fichier faux soit refusé.
"""
from datetime import date, datetime
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest

from apps.fiscal_pt import saft, schema


@pytest.fixture(scope='module')
def modele():
    return schema.charger()


# ── Les données d'un fichier complet ─────────────────────────────────────────

ENTETE = {
    'nif': '123456789', 'nom': 'Orion Lusitana Lda', 'exercice': '2026',
    'debut': date(2026, 1, 1), 'fin': date(2026, 12, 31),
    'adresse': {'adresse': 'Rua do Comércio 1', 'ville': 'Lisboa',
                'code_postal': '1100-150', 'pays': 'PT'},
    'numero_de_certificat': '0',
}
CLIENTS = [{'identifiant': 'C1', 'nom': 'Cliente Lda', 'nif': '500000000',
            'adresse': {'adresse': 'Av. da Liberdade 2', 'ville': 'Lisboa',
                        'code_postal': '1250-096'}}]
PRODUITS = [{'code': 'P1', 'description': 'Prestação de serviços'}]
TAUX = [('NOR', Decimal('23'), 'PT'), ('ISE', Decimal('0'), 'PT')]

LIGNE = {'code_produit': 'P1', 'description': 'Prestação', 'quantite': 1,
         'prix_unitaire': Decimal('100.00'), 'date': date(2026, 3, 7),
         'montant': Decimal('100.00'), 'taux': Decimal('23'),
         'code_de_taux': 'NOR'}

FACTURE = {
    'numero': 'FT A/1', 'atcud': 'CSDF7T5H-1', 'signature': 'S' * 172,
    'version_cle': 1, 'date': date(2026, 3, 7), 'type': 'FT',
    'horodatage': datetime(2026, 3, 7, 10, 30, 0), 'client': 'C1',
    'lignes': [LIGNE], 'total_base': Decimal('100.00'),
    'total_taxes': Decimal('23.00'), 'total': Decimal('123.00'),
}

AVOIR = dict(FACTURE, numero='NC A/1', type='NC', motif='Devolução',
             lignes=[dict(LIGNE, document_rectifie='FT A/1',
                          motif_rectification='Devolução')])

EXONEREE = dict(
    FACTURE, numero='FT A/2',
    lignes=[dict(LIGNE, taux=Decimal('0'), code_de_taux='ISE',
                 motif_exoneration='IVA - autoliquidação',
                 code_exoneration='M31')],
    total_taxes=Decimal('0'), total=Decimal('100.00'))


def _fichier(documents):
    return saft.composer(ENTETE, CLIENTS, PRODUITS, TAUX, documents)


# ── 1. Mes listes d'ordre contre le schéma ───────────────────────────────────

LISTES = [
    ('AuditFile/Header', 'ORDRE_ENTETE'),
    ('AuditFile/Header/CompanyAddress', 'ORDRE_ADRESSE'),
    ('AuditFile/MasterFiles/Customer', 'ORDRE_CLIENT'),
    ('AuditFile/MasterFiles/Product', 'ORDRE_PRODUIT'),
    ('AuditFile/MasterFiles/TaxTable/TaxTableEntry', 'ORDRE_TAUX'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice', 'ORDRE_DOCUMENT'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/DocumentStatus',
     'ORDRE_ETAT'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/SpecialRegimes',
     'ORDRE_REGIMES'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/Line', 'ORDRE_LIGNE'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/Line/Tax',
     'ORDRE_TAXE_DE_LIGNE'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/DocumentTotals',
     'ORDRE_TOTAUX'),
]


@pytest.mark.parametrize('chemin, constante', LISTES)
def test_chaque_liste_d_ordre_est_celle_du_schema(chemin, constante, modele):
    """LE TEST QUI JUSTIFIE TOUT CE FICHIER.

    Les listes de `saft.py` sont recopiées à la main depuis le schéma.
    Ici elles sont comparées au schéma LUI-MÊME, élément par élément et
    dans l'ordre. Un élément ajouté au mauvais rang, ou déplacé par une
    version future du schéma, se voit donc ici — et non dans le courriel
    de rejet de l'AT.
    """
    attendu = modele.ordre(chemin)
    assert attendu is not None, f'Chemin absent du schéma : {chemin}'

    assert list(getattr(saft, constante)) == list(attendu)


def test_le_schema_declare_bien_quatre_lignes_differentes(modele):
    """LA RAISON POUR LAQUELLE LE MODÈLE EST INDEXÉ PAR CHEMIN.

    Le schéma définit quatre `Line`, une par famille de documents. Celui
    des mouvements de marchandises n'a ni `TaxBase` ni `References` ;
    celui des paiements n'a même pas de `ProductCode`.

    Un validateur qui chercherait les définitions par NOM en prendrait
    une au hasard — et accepterait un fichier faux, ou refuserait un
    fichier juste.
    """
    lignes = {c: v for c, v in modele.enfants.items() if c.endswith('/Line')}

    assert len(lignes) == 4

    ventes = lignes[
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/Line']
    mouvements = lignes[
        'AuditFile/SourceDocuments/MovementOfGoods/StockMovement/Line']
    paiements = lignes['AuditFile/SourceDocuments/Payments/Payment/Line']

    assert 'References' in ventes
    assert 'References' not in mouvements
    assert 'ProductCode' not in paiements


def test_le_modele_connait_tout_le_schema(modele):
    """Garde-fou contre le pire défaut possible : un validateur qui ne
    connaît presque rien accepte tout."""
    assert len(modele.enfants) >= schema.CHEMINS_MINIMAUX
    assert 'AuditFile/Header' in modele.enfants
    assert 'AuditFile/SourceDocuments/SalesInvoices/Invoice' in modele.enfants


def test_un_schema_tronque_est_refuse(tmp_path):
    """Le plancher doit MORDRE. Sans lui, une lecture du schéma qui
    échouerait silencieusement rendrait un validateur muet."""
    bidon = tmp_path / 'faux.xsd'
    bidon.write_text(
        '<?xml version="1.0"?>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="AuditFile"><xs:complexType><xs:sequence>'
        '<xs:element name="Header" type="xs:string"/>'
        '</xs:sequence></xs:complexType></xs:element></xs:schema>',
        encoding='utf-8')

    with pytest.raises(schema.ErreurDeSchema, match='chemin'):
        schema.charger(bidon)


def test_un_fichier_qui_n_est_pas_un_schema_saft_est_refuse(tmp_path):
    bidon = tmp_path / 'autre.xsd'
    bidon.write_text(
        '<?xml version="1.0"?>'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">'
        '<xs:element name="Autre" type="xs:string"/></xs:schema>',
        encoding='utf-8')

    with pytest.raises(schema.ErreurDeSchema, match='AuditFile'):
        schema.charger(bidon)


# ── 2. Les fichiers produits passent le schéma ───────────────────────────────

@pytest.mark.parametrize('nom, documents', [
    ('une facture', [FACTURE]),
    ('une facture et son avoir', [FACTURE, AVOIR]),
    ('une ligne exonérée', [EXONEREE]),
    ('les trois ensemble', [FACTURE, EXONEREE, AVOIR]),
])
def test_un_fichier_produit_est_conforme(nom, documents, modele):
    """L'épreuve réelle : le fichier que l'ERP remettrait à
    l'administration, comparé au schéma de l'administration."""
    anomalies = schema.valider(_fichier(documents), modele)

    assert anomalies == [], '\n'.join(str(a) for a in anomalies)


def test_le_resume_dit_ce_qui_n_est_pas_verifie():
    """Annoncer « conforme » sans dire ce qui n'est pas contrôlé serait
    trompeur : les types simples — longueurs, motifs, énumérations — ne
    sont pas vérifiés ici, et l'AT les vérifie."""
    message = schema.resume([])

    assert 'conforme' in message
    assert 'types simples' in message


# ── 3. Le validateur attrape vraiment les erreurs ────────────────────────────

def _casser(documents, transformation):
    """Produit un fichier, le casse, et rend les anomalies."""
    racine = ET.fromstring(_fichier(documents))
    transformation(racine)
    return schema.valider(ET.tostring(racine, encoding='utf-8'))


def _etiquette(nom):
    return f'{{{saft.ESPACE_DE_NOMS}}}{nom}'


def test_un_element_deplace_est_detecte():
    """LE DÉFAUT QUE TOUT CECI SERT À ATTRAPER.

    Un élément hors séquence fait rejeter le fichier ENTIER, et le
    message de l'AT désigne l'élément SUIVANT — ce qui envoie chercher la
    cause au mauvais endroit. Le nôtre nomme le fautif et son voisin.
    """
    def intervertir(racine):
        entete = racine.find(_etiquette('Header'))
        version = entete.find(_etiquette('AuditFileVersion'))
        entete.remove(version)
        entete.append(version)          # à la fin, au lieu du début

    anomalies = _casser([FACTURE], intervertir)

    assert anomalies
    messages = ' '.join(str(a) for a in anomalies)
    assert 'AuditFileVersion' in messages
    assert 'avant' in messages


def test_un_element_obligatoire_absent_est_detecte():
    def retirer(racine):
        entete = racine.find(_etiquette('Header'))
        entete.remove(entete.find(_etiquette('TaxRegistrationNumber')))

    anomalies = _casser([FACTURE], retirer)

    assert any('TaxRegistrationNumber' in str(a) and 'obligatoire' in str(a)
               for a in anomalies)


def test_un_element_inconnu_est_detecte():
    """Un nom mal orthographié ne lève rien à l'écriture : il part dans le
    fichier et s'y fait refuser."""
    def ajouter(racine):
        entete = racine.find(_etiquette('Header'))
        ET.SubElement(entete, _etiquette('CompanyNme')).text = 'faute'

    anomalies = _casser([FACTURE], ajouter)

    assert any('CompanyNme' in str(a) and 'inconnu' in str(a)
               for a in anomalies)


def test_les_deux_branches_d_un_choix_ensemble_sont_detectees():
    """`DebitAmount` ET `CreditAmount` sur la même ligne : le schéma n'en
    veut qu'un. Le fichier s'équilibrerait deux fois."""
    def doubler(racine):
        ligne = racine.find(
            f'{_etiquette("SourceDocuments")}/{_etiquette("SalesInvoices")}/'
            f'{_etiquette("Invoice")}/{_etiquette("Line")}')
        debit = ET.Element(_etiquette('DebitAmount'))
        debit.text = '100.00'
        ligne.insert(list(ligne).index(
            ligne.find(_etiquette('CreditAmount'))), debit)

    anomalies = _casser([FACTURE], doubler)

    assert any('qu’un' in str(a) for a in anomalies)


def test_une_ligne_sans_montant_est_detectee():
    """Ni débit ni crédit : le schéma en demande un."""
    def vider(racine):
        ligne = racine.find(
            f'{_etiquette("SourceDocuments")}/{_etiquette("SalesInvoices")}/'
            f'{_etiquette("Invoice")}/{_etiquette("Line")}')
        ligne.remove(ligne.find(_etiquette('CreditAmount')))

    anomalies = _casser([FACTURE], vider)

    assert any('DebitAmount ou CreditAmount' in str(a) for a in anomalies)


def test_un_espace_de_noms_absent_est_detecte():
    """Sans lui, le fichier est rejeté avant toute autre vérification."""
    anomalies = schema.valider(
        b'<AuditFile><Header/></AuditFile>')

    assert any('espace de noms' in str(a).lower() for a in anomalies)


def test_une_racine_fautive_est_detectee():
    anomalies = schema.valider(
        f'<Autre xmlns="{saft.ESPACE_DE_NOMS}"/>'.encode())

    assert any('AuditFile' in str(a) for a in anomalies)


def test_un_xml_illisible_est_dit_sans_lever():
    """Le validateur doit rendre une anomalie, pas exploser : il est
    appelé depuis un écran."""
    anomalies = schema.valider(b'<AuditFile><Header></AuditFile>')

    assert len(anomalies) == 1
    assert 'illisible' in str(anomalies[0])


def test_le_resume_compte_les_anomalies():
    anomalies = schema.valider(b'<AuditFile/>')

    message = schema.resume(anomalies)
    assert 'anomalie' in message
    assert 'rejette le fichier entier' in message
