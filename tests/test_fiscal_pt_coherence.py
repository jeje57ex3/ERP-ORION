"""Ce qu'un schéma ne sait pas dire, et que l'AT vérifie quand même.

POURQUOI CE FICHIER EXISTE

Un XSD décrit une forme. Il ne sait pas dire que `GrossTotal` doit égaler
`NetTotal` plus `TaxPayable`, ni qu'un `ProductCode` employé sur une ligne
doit figurer dans le référentiel.

Le validateur de l'AT, lui, vérifie les deux. Un fichier qui passe le
schéma et échoue ici est rejeté tout autant — et le motif du rejet est
alors bien plus difficile à comprendre, parce qu'il parle de cohérence et
non de structure.

LA FORME DE CES TESTS

Chacun part d'un fichier CONFORME, le casse d'une seule façon, et vérifie
que l'incohérence est nommée. C'est la seule façon de prouver qu'un
contrôle mord : un test qui se contenterait de valider un bon fichier
passerait aussi avec un module vide.
"""
from datetime import date, datetime
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest

from apps.fiscal_pt import coherence, saft, schema

E = f'{{{saft.ESPACE_DE_NOMS}}}'

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
TAUX = [('NOR', Decimal('23'), 'PT'), ('RED', Decimal('6'), 'PT')]

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


def _racine(documents=None):
    return ET.fromstring(saft.composer(
        ENTETE, CLIENTS, PRODUITS, TAUX,
        documents if documents is not None else [FACTURE]))


def _casser(transformation, documents=None):
    """Produit un fichier conforme, le casse d'une seule façon, et rend
    les incohérences."""
    racine = _racine(documents)
    transformation(racine)
    return coherence.verifier(racine)


def _champ(racine, chemin):
    return racine.find('/'.join(E + nom for nom in chemin.split('/')))


DOCUMENT = 'SourceDocuments/SalesInvoices/Invoice'


# ── Un fichier juste passe ───────────────────────────────────────────────────

@pytest.mark.parametrize('nom, documents', [
    ('une facture', [FACTURE]),
    ('une facture et son avoir', [FACTURE, AVOIR]),
    ('trois factures', [dict(FACTURE, numero=f'FT A/{n}') for n in (1, 2, 3)]),
])
def test_un_fichier_produit_est_coherent(nom, documents):
    anomalies = coherence.verifier(_racine(documents))

    assert anomalies == [], '\n'.join(str(a) for a in anomalies)


def test_un_fichier_coherent_passe_aussi_le_schema():
    """Les deux contrôles doivent s'accorder : un fichier qui passerait
    l'un et pas l'autre signalerait que l'un des deux se trompe."""
    racine = _racine([FACTURE, AVOIR])

    assert schema.valider(racine) == []
    assert coherence.verifier(racine) == []


# ── L'arithmétique d'un document ─────────────────────────────────────────────

def test_un_total_general_faux_est_detecte():
    """`GrossTotal` doit valoir `NetTotal` plus `TaxPayable`. Exactement :
    les trois nombres sont écrits par nous, et un écart signifie que l'un
    a été calculé autrement que les autres."""
    def fausser(racine):
        _champ(racine, f'{DOCUMENT}/DocumentTotals/GrossTotal').text = '999.00'

    anomalies = _casser(fausser)

    assert any('GrossTotal' in str(a) for a in anomalies)


def test_un_total_hors_taxe_qui_ne_suit_pas_les_lignes_est_detecte():
    """L'INCOHÉRENCE LA PLUS COURANTE.

    Elle vient d'un cumul tenu à part qui a dérivé — après la suppression
    d'une ligne, par exemple. Le document reste parfaitement présentable,
    et le fichier est rejeté.
    """
    def fausser(racine):
        totaux = _champ(racine, f'{DOCUMENT}/DocumentTotals')
        totaux.find(f'{E}NetTotal').text = '90.00'
        totaux.find(f'{E}GrossTotal').text = '113.00'   # reste cohérent

    anomalies = _casser(fausser)

    assert any('NetTotal' in str(a) and 'somme' in str(a)
               for a in anomalies)


def test_une_tva_qui_ne_suit_pas_les_taux_est_detectee():
    def fausser(racine):
        totaux = _champ(racine, f'{DOCUMENT}/DocumentTotals')
        totaux.find(f'{E}TaxPayable').text = '6.00'
        totaux.find(f'{E}GrossTotal').text = '106.00'

    anomalies = _casser(fausser)

    assert any('TaxPayable' in str(a) for a in anomalies)


def test_un_centime_d_arrondi_est_tolere():
    """LA TOLÉRANCE N'EST PAS DU LAXISME.

    La TVA se calcule ligne par ligne, chaque ligne arrondie au centime.
    La somme des arrondis diffère parfois d'un centime de la TVA calculée
    sur le total : c'est de l'arithmétique, pas une erreur. Refuser cela
    rendrait le contrôle inutilisable.
    """
    def decaler(racine):
        totaux = _champ(racine, f'{DOCUMENT}/DocumentTotals')
        totaux.find(f'{E}TaxPayable').text = '23.01'
        totaux.find(f'{E}GrossTotal').text = '123.01'

    assert _casser(decaler) == []


def test_un_ecart_de_plus_d_un_centime_par_ligne_est_refuse():
    """La tolérance est d'un centime PAR LIGNE, et pas davantage : une
    tolérance large laisserait passer une vraie incohérence."""
    def decaler(racine):
        totaux = _champ(racine, f'{DOCUMENT}/DocumentTotals')
        totaux.find(f'{E}TaxPayable').text = '23.50'
        totaux.find(f'{E}GrossTotal').text = '123.50'

    assert _casser(decaler)


def test_un_montant_porte_du_mauvais_cote_est_nomme_comme_tel():
    """LE MESSAGE COMPTE AUTANT QUE LA DÉTECTION.

    Un montant d'avoir mis au crédit donne un fichier qui s'équilibre à
    l'envers. Dire « total incohérent » enverrait chercher une erreur de
    calcul ; dire « montant du mauvais côté » désigne la cause.
    """
    def inverser(racine):
        ligne = _champ(racine, f'{DOCUMENT}/Line')
        debit = ligne.find(f'{E}DebitAmount')
        debit.tag = f'{E}CreditAmount'

    anomalies = _casser(inverser, [AVOIR])

    assert any('mauvais' in str(a) or 'CreditAmount' in str(a)
               for a in anomalies)


def test_un_total_absent_le_dit_plutot_que_de_valoir_zero():
    """Un champ absent et un champ à zéro ne disent pas la même chose :
    les confondre ferait passer un total manquant pour un total nul, donc
    équilibré."""
    def retirer(racine):
        totaux = _champ(racine, f'{DOCUMENT}/DocumentTotals')
        totaux.remove(totaux.find(f'{E}NetTotal'))

    anomalies = _casser(retirer)

    assert any('absent' in str(a) or 'illisible' in str(a)
               for a in anomalies)


# ── Les totaux du fichier ────────────────────────────────────────────────────

def test_un_nombre_de_documents_faux_est_detecte():
    def fausser(racine):
        _champ(racine, 'SourceDocuments/SalesInvoices/NumberOfEntries'
               ).text = '7'

    anomalies = _casser(fausser)

    assert any('NumberOfEntries' in str(a) for a in anomalies)


def test_un_total_de_credit_faux_est_detecte():
    def fausser(racine):
        _champ(racine, 'SourceDocuments/SalesInvoices/TotalCredit'
               ).text = '1.00'

    anomalies = _casser(fausser)

    assert any('TotalCredit' in str(a) for a in anomalies)


def test_les_totaux_separent_bien_le_debit_du_credit():
    """Une facture au crédit, un avoir au débit. Les additionner du même
    côté donnerait un fichier qui paraît équilibré et ne l'est pas."""
    racine = _racine([FACTURE, AVOIR])
    ventes = _champ(racine, 'SourceDocuments/SalesInvoices')

    assert ventes.find(f'{E}TotalCredit').text == '100.00'
    assert ventes.find(f'{E}TotalDebit').text == '100.00'
    assert coherence.verifier(racine) == []


# ── Le référentiel ───────────────────────────────────────────────────────────

def test_un_produit_hors_referentiel_est_detecte():
    """L'OUBLI LE PLUS FRÉQUENT. Les documents sont justes, le référentiel
    est incomplet, et le fichier est rejeté en entier."""
    def fausser(racine):
        _champ(racine, f'{DOCUMENT}/Line/ProductCode').text = 'INCONNU'

    anomalies = _casser(fausser)

    assert any('INCONNU' in str(a) and 'MasterFiles' in str(a)
               for a in anomalies)


def test_un_client_hors_referentiel_est_detecte():
    def fausser(racine):
        _champ(racine, f'{DOCUMENT}/CustomerID').text = 'C9'

    anomalies = _casser(fausser)

    assert any('C9' in str(a) for a in anomalies)


def test_un_taux_hors_table_est_detecte():
    def fausser(racine):
        _champ(racine, f'{DOCUMENT}/Line/Tax/TaxCode').text = 'OUT'

    anomalies = _casser(fausser)

    assert any('OUT' in str(a) for a in anomalies)


def test_un_taux_de_la_bonne_region_mais_pas_declare_est_detecte():
    """Le couple (code, région) compte, pas le code seul : le même « NOR »
    déclaré pour le continent ne couvre pas Madère."""
    def fausser(racine):
        _champ(racine, f'{DOCUMENT}/Line/Tax/TaxCountryRegion'
               ).text = 'PT-MA'

    anomalies = _casser(fausser)

    assert any('PT-MA' in str(a) for a in anomalies)


# ── Les dates et la période ──────────────────────────────────────────────────

def test_un_document_hors_periode_est_detecte():
    def fausser(racine):
        _champ(racine, f'{DOCUMENT}/InvoiceDate').text = '2025-03-07'

    anomalies = _casser(fausser)

    assert any('avant le début' in str(a) for a in anomalies)


def test_un_document_apres_la_fin_de_periode_est_detecte():
    def fausser(racine):
        _champ(racine, f'{DOCUMENT}/InvoiceDate').text = '2027-01-15'

    anomalies = _casser(fausser)

    assert any('après la fin' in str(a) for a in anomalies)


def test_une_periode_qui_n_est_pas_le_mois_du_document_est_detectee():
    """Une période fausse ne casse ni le schéma ni l'arithmétique : elle
    range le document dans le mauvais mois, et l'écart n'apparaît qu'au
    rapprochement des déclarations de TVA."""
    def fausser(racine):
        _champ(racine, f'{DOCUMENT}/Period').text = '7'

    anomalies = _casser(fausser)

    assert any('Period' in str(a) for a in anomalies)


def test_un_document_enregistre_avant_sa_propre_date_est_detecte():
    """Le signe d'une antidate — exactement ce que la chaîne de
    signatures sert à empêcher."""
    def fausser(racine):
        _champ(racine, f'{DOCUMENT}/SystemEntryDate').text = (
            '2026-03-01T10:30:00')

    anomalies = _casser(fausser)

    assert any('avant sa propre date' in str(a) for a in anomalies)


def test_un_horodatage_le_jour_meme_est_accepte():
    """Enregistré le jour du document : le cas normal, qu'un contrôle trop
    strict refuserait."""
    def meme_jour(racine):
        _champ(racine, f'{DOCUMENT}/SystemEntryDate').text = (
            '2026-03-07T23:59:59')

    assert _casser(meme_jour) == []


# ── Le résumé ────────────────────────────────────────────────────────────────

def test_le_resume_annonce_ce_qui_a_ete_verifie():
    message = coherence.resume([])

    assert 'totaux' in message
    assert 'référentiel' in message


def test_le_resume_explique_pourquoi_cela_compte():
    """Un message qui dit seulement « 3 incohérences » n'aide pas à
    comprendre qu'un fichier conforme peut tout de même être rejeté."""
    message = coherence.resume(coherence.verifier(_racine([
        dict(FACTURE, total=Decimal('1.00'))])))

    assert 'rejeté' in message


# ── L'enchaînement des deux contrôles ────────────────────────────────────────

def test_la_coherence_ne_se_verifie_qu_apres_la_structure():
    """CE QUE CET ORDRE ÉVITE.

    Sur un fichier dont les totaux manquent, les contrôles arithmétiques
    crieraient à l'incohérence pour chacun — une avalanche de messages
    dont aucun ne désigne la cause réelle, qui est structurelle.

    Le test vérifie que le défaut structurel est bien vu par `schema` ;
    l'écran, lui, s'arrête là et ne lance pas la cohérence.
    """
    racine = _racine()
    totaux = _champ(racine, f'{DOCUMENT}/DocumentTotals')
    totaux.remove(totaux.find(f'{E}GrossTotal'))

    anomalies_de_structure = schema.valider(racine)

    assert any('GrossTotal' in str(a) and 'obligatoire' in str(a)
               for a in anomalies_de_structure)
