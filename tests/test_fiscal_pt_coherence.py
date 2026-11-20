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


# ── Ce que le type du document impose, et que le schéma laisse passer ────────
#
# `References` d'une ligne et `Payment` des totaux sont tous deux
# OPTIONNELS au schéma, parce qu'ils ne le sont pas pour tous les types.
# Le XSD ne sait pas écrire « obligatoire quand InvoiceType vaut ND »,
# alors il n'exige rien. Chacun des fichiers cassés ci-dessous est donc
# CONFORME AU SCHÉMA, et c'est ce que chaque test vérifie d'abord.

NOTE_DE_DEBIT = dict(
    FACTURE, numero='ND A/1', type='ND', motif='Acerto de medição',
    lignes=[dict(LIGNE, document_rectifie='FT A/1',
                 motif_rectification='Acerto de medição')])

FACTURE_RECU = dict(
    FACTURE, numero='FR A/1', type='FR',
    paiements=[{'mecanisme': 'NU', 'montant': Decimal('123.00'),
                'date': date(2026, 3, 7)}])

SIMPLIFIEE = dict(FACTURE, numero='FS A/1', type='FS')


@pytest.mark.parametrize('nom, document', [
    ('facture simplifiée', SIMPLIFIEE),
    ('facture-reçu', FACTURE_RECU),
    ('note de débit', NOTE_DE_DEBIT),
])
def test_les_trois_nouveaux_types_passent_les_deux_controles(nom, document):
    racine = _racine([FACTURE, document])

    assert schema.valider(racine) == []
    assert coherence.verifier(racine) == []


def test_la_note_de_debit_va_bien_au_credit():
    """Elle RECTIFIE comme un avoir et se compte comme une facture.

    Une note de débit augmente ce que le client doit. La porter au débit
    avec les avoirs donnerait un fichier qui s'équilibre à l'envers — et
    le validateur de l'AT ne le dit pas.
    """
    racine = _racine([FACTURE, NOTE_DE_DEBIT])
    ventes = racine.find(f'{E}SourceDocuments/{E}SalesInvoices')

    assert ventes.find(f'{E}TotalCredit').text == '200.00'
    assert ventes.find(f'{E}TotalDebit').text == '0.00'
    assert coherence.verifier(racine) == []


@pytest.mark.parametrize('type_document, document', [
    ('NC', AVOIR),
    ('ND', NOTE_DE_DEBIT),
])
def test_un_rectificatif_sans_reference_est_detecte(type_document, document):
    racine = _racine([FACTURE, document])
    for ligne in racine.iter(f'{E}Line'):
        renvoi = ligne.find(f'{E}References')
        if renvoi is not None:
            ligne.remove(renvoi)

    assert schema.valider(racine) == [], 'le schéma, lui, accepte'
    anomalies = coherence.verifier(racine)

    assert any('36' in str(a) for a in anomalies), \
        '\n'.join(str(a) for a in anomalies) or 'aucune anomalie'


def test_la_facture_recu_sans_paiement_est_detectee():
    racine = _racine([FACTURE_RECU])
    for totaux in racine.iter(f'{E}DocumentTotals'):
        totaux.remove(totaux.find(f'{E}Payment'))

    assert schema.valider(racine) == [], 'le schéma, lui, accepte'
    anomalies = coherence.verifier(racine)

    assert any('quittance' in str(a) for a in anomalies)


@pytest.mark.parametrize('montant, attendu', [
    ('100.00', 'inférieure'),
    ('200.00', 'supérieure'),
])
def test_un_encaissement_qui_ne_solde_pas_le_total_est_detecte(montant,
                                                               attendu):
    racine = _racine([FACTURE_RECU])
    racine.find(f'.//{E}PaymentAmount').text = montant

    assert schema.valider(racine) == []
    anomalies = coherence.verifier(racine)

    assert any(attendu in str(a) for a in anomalies)


def test_un_paiement_sur_un_type_qui_n_atteste_rien_est_detecte():
    racine = _racine([FACTURE_RECU])
    racine.find(f'.//{E}InvoiceType').text = 'FT'

    assert schema.valider(racine) == []
    anomalies = coherence.verifier(racine)

    assert any('FR' in str(a) for a in anomalies)


def test_le_paiement_est_range_apres_les_totaux_et_non_a_la_fin():
    """L'ORDRE, encore : `Payment` vient après `GrossTotal`, `Currency` et
    `Settlement` dans la séquence du schéma. Ajouté à la fin du bloc il
    serait au bon endroit par hasard ; rangé par `ORDRE_TOTAUX` il y est
    par construction, et le restera quand `Currency` apparaîtra."""
    racine = _racine([FACTURE_RECU])
    totaux = racine.find(f'.//{E}DocumentTotals')
    noms = [enfant.tag.replace(E, '') for enfant in totaux]

    assert noms == ['TaxPayable', 'NetTotal', 'GrossTotal', 'Payment']


def test_une_reference_sur_une_facture_ordinaire_n_est_pas_une_anomalie():
    """Ce qui est EXIGÉ d'un rectificatif n'est pas INTERDIT aux autres.

    Une facture peut légitimement renvoyer à un bon de livraison ou à un
    devis. Signaler ce renvoi comme une anomalie apprendrait à ignorer les
    messages du contrôle — ce qui est le seul moyen de rendre un
    validateur inutile sans le casser.
    """
    racine = _racine([dict(
        FACTURE, lignes=[dict(LIGNE, document_rectifie='GR A/7',
                              motif_rectification='Guia de remessa')])])

    assert schema.valider(racine) == []
    assert coherence.verifier(racine) == []


# ── Les reçus (table 4.4) ────────────────────────────────────────────────────

AFFECTATION = {'document': 'FT A/1', 'date': date(2026, 3, 7),
               'montant': Decimal('60.00'), 'au_debit': False,
               'description': 'Adiantamento'}

RECU = {
    'numero': 'RG A/1', 'atcud': 'JFFNVTC7-1',
    'date': date(2026, 3, 20), 'type': 'RG', 'etat': 'N',
    'horodatage': datetime(2026, 3, 20, 9, 30, 0), 'client': 'C1',
    'affectations': [AFFECTATION],
    'paiements': [{'mecanisme': 'TB', 'montant': Decimal('60.00'),
                   'date': date(2026, 3, 20)}],
    'total_base': Decimal('60.00'), 'total_taxes': Decimal('0.00'),
    'total': Decimal('60.00'),
}

RECU_DE_RECU = 'SourceDocuments/Payments/Payment'


def _racine_avec_recu(recus=None, documents=None):
    return ET.fromstring(saft.composer(
        ENTETE, CLIENTS, PRODUITS, TAUX,
        documents if documents is not None else [FACTURE],
        recus if recus is not None else [RECU]))


def _casser_le_recu(transformation, recus=None, documents=None):
    """Un fichier conforme, cassé d'une seule façon.

    On vérifie D'ABORD que le schéma accepte encore le fichier. C'est tout
    l'intérêt de ces tests : sans cela on ne saurait pas si l'anomalie est
    relevée par le contrôle de cohérence, ou si elle aurait été attrapée
    bien plus tôt.
    """
    racine = _racine_avec_recu(recus, documents)
    transformation(racine)
    assert schema.valider(racine) == [], 'le schéma, lui, doit accepter'
    return coherence.verifier(racine)


def test_un_fichier_avec_un_recu_est_coherent():
    racine = _racine_avec_recu()

    assert schema.valider(racine) == []
    anomalies = coherence.verifier(racine)
    assert anomalies == [], '\n'.join(str(a) for a in anomalies)


def test_un_recu_sans_renvoi_au_document_est_detecte():
    """Le numéro du document réglé, perdu en chemin.

    On le VIDE plutôt que de retirer l'élément : un élément absent casse
    le groupe et serait attrapé par le schéma, alors qu'un texte blanc y
    passe. C'est aussi le cas réel — un champ recopié vide.
    """
    def vider(racine):
        _champ(racine,
               f'{RECU_DE_RECU}/Line/SourceDocumentID/OriginatingON').text = ' '

    anomalies = _casser_le_recu(vider)

    assert any('OriginatingON' in str(a) for a in anomalies)


def test_un_recu_sans_moyen_de_paiement_est_detecte():
    """Le schéma rend `PaymentMethod` optionnel ; un reçu, non.

    Un reçu qui ne dit pas comment la somme a été reçue n'atteste rien de
    vérifiable, et le fichier est pourtant parfaitement valide.
    """
    def retirer(racine):
        recu = _champ(racine, RECU_DE_RECU)
        recu.remove(recu.find(f'{E}PaymentMethod'))

    anomalies = _casser_le_recu(retirer)

    assert any('moyen de paiement' in str(a) for a in anomalies)


@pytest.mark.parametrize('montant, sens', [
    ('40.00', 'inférieure'),
    ('80.00', 'supérieure'),
])
def test_un_encaissement_qui_ne_fait_pas_le_total_du_recu_est_detecte(
        montant, sens):
    def fausser(racine):
        _champ(racine,
               f'{RECU_DE_RECU}/PaymentMethod/PaymentAmount').text = montant

    anomalies = _casser_le_recu(fausser)

    assert any(sens in str(a) for a in anomalies)


def test_un_total_de_recu_qui_ne_suit_pas_ses_affectations_est_detecte():
    def fausser(racine):
        _champ(racine, f'{RECU_DE_RECU}/Line/CreditAmount').text = '10.00'

    anomalies = _casser_le_recu(fausser)

    assert any('affectation' in str(a) for a in anomalies)


def test_un_recu_qui_encaisse_et_rembourse_a_la_fois_est_detecte():
    """Le schéma accepte les deux sens dans le même reçu — il offre un
    `choice` par LIGNE, pas par document. Le total unique du reçu ne
    correspond alors à aucun des deux mouvements."""
    mixte = dict(RECU, affectations=[
        dict(AFFECTATION, montant=Decimal('30.00')),
        dict(AFFECTATION, document='NC A/1', montant=Decimal('30.00'),
             au_debit=True),
    ], total_base=Decimal('0.00'), total=Decimal('0.00'))

    racine = _racine_avec_recu([mixte])
    assert schema.valider(racine) == []
    anomalies = coherence.verifier(racine)

    assert any('encaisse et rembourse' in str(a) for a in anomalies)


def test_un_recu_du_regime_de_tva_de_caisse_sans_taxe_est_detecte():
    """L'`xs:assert` que notre validateur de structure n'évalue pas.

    Le XSD le dit noir sur blanc : « if (../PaymentType eq 'RC' and
    not(Tax)) then false() ». Ce sont des assertions XSD 1.1, que le
    validateur de ce dépôt ne lit pas et que celui de l'AT lit. Le fichier
    passerait donc ici et serait refusé là-bas, pour une règle écrite dans
    le fichier qu'on vient de lire.
    """
    racine = _racine_avec_recu([dict(RECU, type='RC')])

    assert schema.valider(racine) == []
    anomalies = coherence.verifier(racine)

    assert any('RC' in str(a) and 'Tax' in str(a) for a in anomalies)


def test_un_total_de_controle_des_recus_faux_est_detecte():
    def fausser(racine):
        _champ(racine, 'SourceDocuments/Payments/TotalCredit').text = '999.00'

    anomalies = _casser_le_recu(fausser)

    assert any('TotalCredit' in str(a) and 'reçus' in str(a)
               for a in anomalies)


def test_un_nombre_de_recus_annonce_a_faux_est_detecte():
    def fausser(racine):
        _champ(racine,
               'SourceDocuments/Payments/NumberOfEntries').text = '7'

    anomalies = _casser_le_recu(fausser)

    assert any('NumberOfEntries' in str(a) for a in anomalies)


def test_un_recu_dont_le_client_n_est_pas_declare_est_detecte():
    def fausser(racine):
        _champ(racine, f'{RECU_DE_RECU}/CustomerID').text = 'C999'

    anomalies = _casser_le_recu(fausser)

    assert any('C999' in str(a) for a in anomalies)


# ── Les totaux de contrôle excluent ce que le nombre de registres compte ─────

ANNULEE = dict(FACTURE, numero='FT A/2', atcud='CSDF7T5H-2', etat='A',
               lignes=[LIGNE])


def test_un_document_annule_est_compte_mais_pas_additionne():
    """Portaria n.º 302/2016, champs 4.1.1 à 4.1.3.

    `NumberOfEntries` « deve conter o número total de documentos,
    INCLUINDO os documentos cujo valor do campo Estado atual
    (InvoiceStatus) seja do tipo "A" ou "F" » ; `TotalDebit` et
    `TotalCredit` somment « dela EXCLUINDO » ces mêmes documents.

    Deux règles opposées sur les mêmes documents : l'annulé reste dans le
    fichier pour prouver que la série ne saute aucun numéro, et son
    montant ne compte plus. Le composeur sommait tout, et le contrôle de
    cohérence appliquait la MÊME règle fausse — donc il confirmait le
    fichier que l'AT refusait.
    """
    racine = _racine([FACTURE, ANNULEE])
    ventes = _champ(racine, 'SourceDocuments/SalesInvoices')

    assert ventes.find(f'{E}NumberOfEntries').text == '2'
    assert ventes.find(f'{E}TotalCredit').text == '100.00'
    assert coherence.verifier(racine) == []


def test_un_document_facture_est_exclu_lui_aussi():
    """« F » — document déjà facturé ailleurs — est exclu au même titre que
    « A ». Les deux états sont nommés ensemble par le texte."""
    facturee = dict(FACTURE, numero='FT A/3', atcud='CSDF7T5H-3', etat='F',
                    lignes=[LIGNE])
    racine = _racine([FACTURE, facturee])
    ventes = _champ(racine, 'SourceDocuments/SalesInvoices')

    assert ventes.find(f'{E}NumberOfEntries').text == '2'
    assert ventes.find(f'{E}TotalCredit').text == '100.00'
    assert coherence.verifier(racine) == []


def test_un_total_qui_inclurait_un_document_annule_est_detecte():
    """La preuve que le contrôle mord désormais : on remet l'ancien total.

    200,00 € est exactement ce que le composeur écrivait avant — la somme
    des deux documents, annulé compris.
    """
    racine = _racine([FACTURE, ANNULEE])
    _champ(racine,
           'SourceDocuments/SalesInvoices/TotalCredit').text = '200.00'
    assert schema.valider(racine) == []

    anomalies = coherence.verifier(racine)
    assert any('TotalCredit' in str(a) and 'non annulés' in str(a)
               for a in anomalies)


def test_un_recu_annule_est_compte_mais_pas_additionne():
    """Pour un reçu, seul « A » existe : `PaymentStatus` n'énumère que
    « N » et « A », là où un document de facturation exclut aussi « F »."""
    annule = dict(RECU, numero='RG A/2', atcud='JFFNVTC7-2', etat='A')
    racine = _racine_avec_recu([RECU, annule])
    table = _champ(racine, 'SourceDocuments/Payments')

    assert table.find(f'{E}NumberOfEntries').text == '2'
    assert table.find(f'{E}TotalCredit').text == '60.00'
    assert coherence.verifier(racine) == []


def test_une_reference_faite_d_espaces_ne_vaut_pas_reference():
    """Les champs texte du SAF-T ont une longueur MINIMALE de 1.

    Une seule espace la respecte : « <Reference> </Reference> » passe le
    schéma. Un contrôle qui testerait seulement la présence de l'élément
    la laisserait passer aussi, et l'avoir resterait orphelin dans le
    fichier tout en ayant l'air de désigner quelque chose.

    Ce trou a été trouvé par le test du renvoi d'un reçu, qui vidait le
    champ au lieu de retirer l'élément — parce que retirer l'élément
    aurait été attrapé par le schéma, donc n'aurait rien prouvé. Le même
    trou existait sur la référence des documents rectificatifs.
    """
    def vider(racine):
        _champ(racine, f'{DOCUMENT}/Line/References/Reference').text = '   '

    racine = _racine([AVOIR])
    vider(racine)
    assert schema.valider(racine) == [], 'le schéma, lui, doit accepter'

    anomalies = coherence.verifier(racine)
    assert any('36.º' in str(a) for a in anomalies)
