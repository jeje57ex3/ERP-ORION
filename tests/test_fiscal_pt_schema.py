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
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/DocumentTotals/Payment',
     'ORDRE_PAIEMENT'),
    # La table 4.4, dont AUCUNE liste ne peut etre reprise de la 4.1 :
    # la ligne n'a pas de produit, l'etat s'appelle autrement, et les
    # totaux rangent « Settlement » avant « Currency » au lieu de l'inverse.
    ('AuditFile/SourceDocuments/Payments/Payment', 'ORDRE_RECU'),
    ('AuditFile/SourceDocuments/Payments/Payment/DocumentStatus',
     'ORDRE_ETAT_DE_RECU'),
    ('AuditFile/SourceDocuments/Payments/Payment/PaymentMethod',
     'ORDRE_PAIEMENT'),
    ('AuditFile/SourceDocuments/Payments/Payment/Line',
     'ORDRE_LIGNE_DE_RECU'),
    ('AuditFile/SourceDocuments/Payments/Payment/Line/SourceDocumentID',
     'ORDRE_DOCUMENT_SOURCE'),
    ('AuditFile/SourceDocuments/Payments/Payment/DocumentTotals',
     'ORDRE_TOTAUX_DE_RECU'),
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
    trompeur. Les valeurs sont désormais vérifiées ; restent les règles
    qu'un XSD ne sait pas exprimer — cohérence des totaux, unicité des
    numéros, continuité des séries."""
    message = schema.resume([])

    assert 'Conforme' in message
    assert 'totaux' in message
    assert 'séries' in message


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


# ── 4. Mes constantes contre les énumérations du schéma ──────────────────────

def test_les_types_de_document_sont_admis_par_le_schema(modele):
    """LES TESTS LES PLUS UTILES DE CE FICHIER.

    `TYPES_DE_DOCUMENT` est écrit à la main dans `models.py`. Le schéma,
    lui, énumère les quinze valeurs qu'il accepte pour `InvoiceType`. Un
    type inventé — « FAC », par réflexe français — serait accepté à la
    saisie, signé, imprimé, et refusé à la remise du fichier.
    """
    from apps.fiscal_pt.models import TYPES_DE_DOCUMENT

    admis = set(modele.contraintes(
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/InvoiceType'
    )['enumeration'])

    assert admis, 'Énumération du schéma non lue : test sans valeur.'
    miens = {code for code, _ in TYPES_DE_DOCUMENT}
    assert miens <= admis, f'Types inconnus du schéma : {miens - admis}'


def test_les_etats_de_document_sont_admis_par_le_schema(modele):
    from apps.fiscal_pt.models import ETATS_DE_DOCUMENT

    admis = set(modele.contraintes(
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/DocumentStatus'
        '/InvoiceStatus')['enumeration'])

    assert admis
    miens = {code for code, _ in ETATS_DE_DOCUMENT}
    assert miens <= admis, f'États inconnus du schéma : {miens - admis}'


def test_la_base_comptable_est_admise_par_le_schema(modele):
    admis = set(modele.contraintes(
        'AuditFile/Header/TaxAccountingBasis')['enumeration'])

    assert saft.BASE_COMPTABLE in admis


def test_la_version_annoncee_est_celle_que_le_schema_exige(modele):
    """Le schéma porte un motif figé pour `AuditFileVersion` : annoncer
    une autre version fait rejeter le fichier dès la première ligne."""
    import re

    motif = modele.contraintes(
        'AuditFile/Header/AuditFileVersion')['pattern'][0]

    assert re.fullmatch(motif, saft.VERSION)


def test_les_regions_fiscales_sont_admises_par_le_schema(modele):
    """« PT-AC » et « PT-MA » ne sont pas des codes ISO : le schéma les
    ajoute explicitement à la liste pour `TaxCountryRegion`. Les employer
    dans un champ `Country` serait refusé."""
    import re

    from apps.fiscal_pt import taxas

    motif = modele.contraintes(
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/Line/Tax'
        '/TaxCountryRegion')['pattern'][0]

    for region, _ in taxas.REGIONS:
        assert re.fullmatch(motif, region), region


def test_les_codes_de_taux_sont_admis_par_le_schema(modele):
    import re

    motif = modele.contraintes(
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/Line/Tax/TaxCode'
    )['pattern'][0]

    for code in saft.CODES_DE_TAUX.values():
        assert re.fullmatch(motif, code), code


def test_les_codes_d_exoneration_suivent_le_format_du_schema(modele):
    """Le schéma ne vérifie que la FORME : il accepterait M03 et M08, qui
    n'existent pas. Notre table est donc plus stricte que lui — c'est
    voulu —, mais elle doit au moins respecter la forme."""
    import re

    from apps.fiscal_pt import isencao

    motif = modele.contraintes(
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/Line'
        '/TaxExemptionCode')['pattern'][0]

    for code in isencao.CODES:
        assert re.fullmatch(motif, code), code

    # La preuve que le schéma est plus permissif que nous.
    assert re.fullmatch(motif, 'M08')
    assert 'M08' not in isencao.CODES


def test_les_mentions_d_exoneration_tiennent_dans_le_champ(modele):
    """`TaxExemptionReason` a une longueur minimale ET maximale. Plusieurs
    mentions officielles frôlent la limite haute ; une seule qui la
    dépasserait ferait rejeter le fichier entier."""
    from apps.fiscal_pt import isencao

    contraintes = modele.contraintes(
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/Line'
        '/TaxExemptionReason')
    minimum = int(contraintes['minLength'])
    maximum = int(contraintes['maxLength'])

    for code in isencao.CODES:
        mencao = isencao.mencao_saft(code)
        assert minimum <= len(mencao) <= maximum, (
            f'{code} : « {mencao} » fait {len(mencao)} caractères, '
            f'hors de [{minimum}, {maximum}]')


def test_deux_documents_officiels_se_contredisent_sur_m15(modele):
    """LA CONTRADICTION QUE CE TEST FIGE.

    La table des motifs publie pour M15 une mention de 61 caractères.
    Le schéma SAF-T plafonne `TaxExemptionReason` à 60. Une entreprise qui
    facture des objets d'art sous le régime de la marge produirait donc un
    fichier rejeté — en employant le texte publié par l'administration
    elle-même.

    Ce test garde la mesure. Si une version future de la table raccourcit
    la mention, ou si le schéma élargit le champ, il échouera — et
    l'abrègement pourra être retiré.
    """
    from apps.fiscal_pt import isencao

    maximum = int(modele.contraintes(
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/Line'
        '/TaxExemptionReason')['maxLength'])

    officielle = isencao.CODES['M15'][0]
    assert len(officielle) == 61
    assert len(officielle) > maximum

    abregee = isencao.mencao_saft('M15')
    assert len(abregee) <= maximum
    # Tous les mots sont conservés : on n'a pas tronqué au milieu d'un mot.
    assert 'antiguidades' in abregee
    assert 'coleção' in abregee


def test_m15_est_le_seul_a_devoir_etre_abrege(modele):
    """Si une autre mention passait la limite, l'abrègement tacite d'une
    seule donnerait un faux sentiment de sécurité."""
    from apps.fiscal_pt import isencao

    maximum = int(modele.contraintes(
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/Line'
        '/TaxExemptionReason')['maxLength'])

    trop_longues = {code for code, (mencao, _) in isencao.CODES.items()
                    if len(mencao) > maximum}

    assert trop_longues == set(isencao.MENTION_SAFT_ABREGEE)


def test_la_mention_imprimee_reste_celle_de_la_table():
    """L'abrègement ne concerne QUE le champ du fichier : c'est la
    mention de la table qui a valeur légale sur le document imprimé."""
    from apps.fiscal_pt import isencao

    assert isencao.mencao('M15') == (
        'Regime da margem de lucro – Objetos de coleção e antiguidades')
    assert isencao.mencao('M15') != isencao.mencao_saft('M15')

    # Pour tous les autres, les deux sont identiques.
    for code in isencao.CODES:
        if code not in isencao.MENTION_SAFT_ABREGEE:
            assert isencao.mencao(code) == isencao.mencao_saft(code)


def test_le_motif_de_numero_est_exactement_celui_du_schema(modele):
    """L'ACCENT CIRCONFLEXE EXCLU N'EST PAS UN DÉTAIL DE COPIE.

    Une première version du motif écrivait « [^/ ]+ » au lieu de
    « [^/^ ]+ », ce qui laissait passer une série nommée « A^B » : le
    numéro était accepté par l'ERP et refusé par le schéma.
    """
    from apps.fiscal_pt.models import MOTIF_NUMERO_SAFT

    attendu = modele.contraintes(
        'AuditFile/SourceDocuments/SalesInvoices/Invoice/InvoiceNo'
    )['pattern'][0]

    assert MOTIF_NUMERO_SAFT.pattern == attendu


def test_une_serie_avec_accent_circonflexe_est_refusee():
    from apps.fiscal_pt.models import MOTIF_NUMERO_SAFT

    assert MOTIF_NUMERO_SAFT.fullmatch('FT A/1')
    assert not MOTIF_NUMERO_SAFT.fullmatch('FT A^B/1')
    assert not MOTIF_NUMERO_SAFT.fullmatch('FAC-2026-0042')


# ── 5. La vérification des valeurs mord-elle vraiment ? ──────────────────────

def test_le_modele_porte_des_contraintes_de_valeur(modele):
    """Garde-fou, encore : une vérification de valeur qui ne connaîtrait
    aucune contrainte accepterait toutes les valeurs, en silence."""
    assert len(modele.facettes) >= 300
    for chemin in ('AuditFile/Header/TaxRegistrationNumber',
                   'AuditFile/Header/AuditFileVersion',
                   'AuditFile/SourceDocuments/SalesInvoices/Invoice/InvoiceNo'):
        assert modele.contraintes(chemin), chemin


@pytest.mark.parametrize('chemin, valeur, extrait', [
    ('AuditFile/Header/TaxRegistrationNumber', '12', 'inférieur'),
    ('AuditFile/Header/AuditFileVersion', '1.03_01', 'format'),
    ('AuditFile/Header/TaxAccountingBasis', 'Z', 'admise'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/InvoiceNo',
     'FAC-2026-0042', 'format'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/InvoiceType',
     'FAC', 'admise'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/DocumentTotals'
     '/GrossTotal', '-10.00', 'inférieur'),
    ('AuditFile/SourceDocuments/SalesInvoices/Invoice/Line'
     '/TaxExemptionCode', 'M3', 'format'),
])
def test_une_valeur_fautive_est_attrapee(chemin, valeur, extrait, modele):
    ecarts = schema.verifier_la_valeur(valeur, modele.contraintes(chemin))

    assert ecarts, f'{chemin} = {valeur!r} passe sans être signalé'
    assert any(extrait in e for e in ecarts), ecarts


def test_les_bornes_numeriques_ne_sont_pas_comparees_comme_du_texte(modele):
    """LE PIÈGE QUE CE TEST FERME.

    Les bornes du schéma sont du TEXTE. Comparées comme telles, « 9 »
    serait supérieur à « 100000000 » — et un NIF à un chiffre passerait.
    """
    contraintes = modele.contraintes('AuditFile/Header/TaxRegistrationNumber')

    assert schema.verifier_la_valeur('9', contraintes)
    assert schema.verifier_la_valeur('99999999', contraintes)
    assert not schema.verifier_la_valeur('123456789', contraintes)


def test_le_schema_distingue_le_pays_du_client_de_celui_de_l_entreprise(
        modele):
    """UNE SUBTILITÉ QUE SEUL LE MODÈLE PAR CHEMIN PEUT VOIR.

    « Desconhecido » est admis pour le pays d'un CLIENT, et refusé pour
    celui de l'entreprise elle-même. Les deux éléments s'appellent
    `Country`. Un validateur indexé par nom se tromperait dans un sens ou
    dans l'autre.
    """
    entreprise = modele.contraintes('AuditFile/Header/CompanyAddress/Country')
    client = modele.contraintes(
        'AuditFile/MasterFiles/Customer/BillingAddress/Country')

    assert schema.verifier_la_valeur('Desconhecido', entreprise)
    assert not schema.verifier_la_valeur('Desconhecido', client)
    assert not schema.verifier_la_valeur('PT', entreprise)
    assert not schema.verifier_la_valeur('PT', client)


def test_un_fichier_avec_une_valeur_fautive_est_refuse():
    """La vérification des valeurs doit être BRANCHÉE dans `valider`, et
    pas seulement disponible à côté."""
    def fausser(racine):
        entete = racine.find(_etiquette('Header'))
        entete.find(_etiquette('TaxRegistrationNumber')).text = '42'

    anomalies = _casser([FACTURE], fausser)

    assert any('TaxRegistrationNumber' in str(a) for a in anomalies)


def test_le_resume_ne_promet_plus_ce_qu_il_ne_tient_pas():
    """Le résumé annonçait « les types simples ne sont pas vérifiés ».
    Ils le sont désormais : laisser l'ancienne phrase ferait chercher
    ailleurs un défaut que ce validateur attrape."""
    message = schema.resume([])

    assert 'structure et valeurs' in message
    assert 'ne sont pas vérifiés' not in message


# ── 6. Le NIF, que le schéma borne et dont il ignore la clé ──────────────────

def test_les_bornes_du_nif_viennent_du_schema(modele):
    """`NIF_MINIMUM` et `NIF_MAXIMUM` sont écrits à la main dans
    `models.py` : ils doivent être ceux du schéma."""
    from apps.fiscal_pt.models import NIF_MAXIMUM, NIF_MINIMUM

    contraintes = modele.contraintes('AuditFile/Header/TaxRegistrationNumber')

    assert int(contraintes['minInclusive']) == NIF_MINIMUM
    assert int(contraintes['maxInclusive']) == NIF_MAXIMUM


@pytest.mark.parametrize('nif', ['123456789', '500000000', '999999990',
                                 '501964843'])
def test_un_nif_valide_est_accepte(nif):
    from apps.fiscal_pt.models import valider_nif

    assert valider_nif(nif) == nif


def test_le_nif_conventionnel_du_consommateur_final_est_valide():
    """« 999999990 » est imposé par la spécification du code QR, et il
    respecte bien le modulo 11 — ce qui n'allait pas de soi."""
    from apps.fiscal_pt.models import valider_nif
    from apps.fiscal_pt.qr import NIF_CONSOMMATEUR_FINAL

    assert valider_nif(NIF_CONSOMMATEUR_FINAL) == NIF_CONSOMMATEUR_FINAL


def test_un_nif_au_chiffre_de_controle_faux_est_refuse():
    """CE QUE LE SCHÉMA NE VOIT PAS.

    « 123456788 » a bien neuf chiffres et respecte les bornes : le
    fichier passerait la validation de l'AT. Le NIF désignerait pourtant
    quelqu'un d'autre, ou personne — et l'erreur n'apparaîtrait que
    lorsque l'administration ne retrouverait pas l'entreprise.
    """
    from django.core.exceptions import ValidationError

    from apps.fiscal_pt.models import valider_nif

    with pytest.raises(ValidationError, match='contrôle'):
        valider_nif('123456788')


@pytest.mark.parametrize('mauvais', ['12345678', '1234567890', 'abcdefghi',
                                     '023456789'])
def test_un_nif_mal_forme_est_refuse(mauvais):
    from django.core.exceptions import ValidationError

    from apps.fiscal_pt.models import valider_nif

    with pytest.raises(ValidationError):
        valider_nif(mauvais)


def test_les_espaces_d_un_nif_sont_normalises():
    """Un NIF se recopie souvent espacé, depuis un courrier ou une carte.
    Le refuser pour cela bloquerait une saisie juste."""
    from apps.fiscal_pt.models import valider_nif

    assert valider_nif('123 456 789') == '123456789'


def test_un_nif_absent_est_refuse_ou_tolere_selon_le_contexte():
    from django.core.exceptions import ValidationError

    from apps.fiscal_pt.models import valider_nif

    with pytest.raises(ValidationError, match='absent'):
        valider_nif('')

    assert valider_nif('', obligatoire=False) == ''
