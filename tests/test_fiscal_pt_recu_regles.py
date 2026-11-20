"""Ce qu'un reçu doit porter — mesuré sans base et sans Django.

POURQUOI CE FICHIER EST SÉPARÉ DE CELUI QUI PASSE PAR LA BASE

Les règles d'un reçu sont de l'arithmétique et des chaînes : un document
réglé, un montant, un sens, une somme encaissée. Elles se mesurent donc
sans migration ni transaction, et c'est ce qui permet d'en écrire
beaucoup.

CE QUE LE SCHÉMA DIT DES REÇUS, ET CE QU'IL NE DIT PAS

Il dit : deux types seulement (`SAFTPTPaymentType`), deux états seulement
(`PaymentStatus`), une ligne au moins, un `SourceDocumentID` par ligne.

Il ne dit pas : qu'un reçu ne peut pas encaisser et rembourser à la fois,
que la somme des moyens de paiement doit égaler le total, qu'un montant
nul n'atteste rien. Ces trois-là sont dans la loi ou dans le bon sens
comptable, et un fichier qui les viole passe le contrôle du schéma.
"""
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from apps.fiscal_pt import assinatura, saft, tipos

XSD = Path('apps/fiscal_pt/schemas/SAFTPT1.04_01.xsd')


def _schema():
    """Le XSD, lu en latin-1.

    Il n'est PAS en UTF-8 : l'octet 0xE7 de « correcção » fait échouer la
    lecture en UTF-8 à la position 98326. Le lire mal ferait échouer ces
    tests pour une raison qui n'a rien à voir avec ce qu'ils mesurent.
    """
    return XSD.read_text(encoding='latin-1')


UNE_AFFECTATION = {'document': 'FT A/1', 'date': date(2026, 3, 7),
                   'montant': Decimal('60.00'), 'type_du_document': 'FT'}


def _affectation(**remplacements):
    return [dict(UNE_AFFECTATION, **remplacements)]


# ── Les types de reçus ───────────────────────────────────────────────────────

def test_les_deux_types_de_recu_sont_ceux_du_schema():
    """Relevés dans l'énumération, et non dans une documentation.

    `SAFTPTPaymentType` n'accepte que deux valeurs. Un troisième type
    inventé serait signé sans protester et ferait refuser l'export entier.
    """
    texte = _schema()
    debut = texte.index('name="SAFTPTPaymentType"')
    bloc = texte[debut:texte.index('</xs:simpleType>', debut)]

    du_schema = set()
    for morceau in bloc.split('<xs:enumeration value="')[1:]:
        du_schema.add(morceau.split('"')[0])

    assert du_schema == {'RG', 'RC'}
    assert set(tipos.CODES_DE_RECU) | {tipos.TYPE_DE_RECU_NON_COUVERT} == \
        du_schema


def test_le_recu_du_regime_de_tva_de_caisse_est_refuse_en_nommant_la_raison():
    """« RC » est connu du schéma et non émis, et le refus le dit.

    Un type offert mais incomplet est le piège exact que la validation du
    type de série a déjà fermé une fois : la série se déclare, les
    documents se signent, et l'export les refuse quand plus rien ne les
    reprend. Le schéma impose à chaque ligne d'un « RC » son bloc `Tax`,
    par un `xs:assert`.
    """
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.valider_le_type_de_recu('RC')

    assert 'IVA de caixa' in str(erreur.value)
    assert '« RG »' in str(erreur.value)


@pytest.mark.parametrize('type_recu', ['RG'])
def test_le_type_emis_est_accepte(type_recu):
    assert tipos.valider_le_type_de_recu(type_recu) == type_recu


@pytest.mark.parametrize('type_recu', ['FT', 'RX', '', 'rg', None])
def test_un_type_de_recu_inconnu_est_refuse(type_recu):
    with pytest.raises(tipos.RegleDeType):
        tipos.valider_le_type_de_recu(type_recu)


def test_un_recu_releve_d_une_autre_table_que_les_factures():
    assert tipos.est_un_recu('RG') is True
    for code in tipos.CODES_DE_TYPE:
        assert tipos.est_un_recu(code) is False


def test_une_serie_peut_porter_un_type_de_recu():
    """Sans quoi aucun reçu ne pourrait être numéroté légalement."""
    codes = [code for code, _ in tipos.TYPES_DE_SERIE]

    assert 'RG' in codes
    for code in tipos.CODES_DE_TYPE:
        assert code in codes


# ── Les états, et les deux listes qui n'en font pas une ──────────────────────

def test_les_etats_de_recu_sont_ceux_du_schema_et_ils_sont_deux():
    texte = _schema()
    debut = texte.index('name="PaymentStatus"')
    bloc = texte[debut:texte.index('</xs:simpleType>', debut)]

    du_schema = {morceau.split('"')[0]
                 for morceau in bloc.split('<xs:enumeration value="')[1:]}

    assert du_schema == {'N', 'A'}
    assert set(tipos.CODES_D_ETAT_DE_RECU) == du_schema


def test_les_etats_de_facturation_sont_ceux_du_schema_et_ils_sont_cinq():
    texte = _schema()
    debut = texte.index('name="InvoiceStatus"')
    bloc = texte[debut:texte.index('</xs:simpleType>', debut)]

    du_schema = {morceau.split('"')[0]
                 for morceau in bloc.split('<xs:enumeration value="')[1:]}

    assert du_schema == {'N', 'S', 'A', 'R', 'F'}
    assert set(tipos.CODES_D_ETAT_DE_FACTURATION) == du_schema


def test_les_deux_listes_d_etats_ne_sont_pas_la_meme():
    """Un test de garde, et il a un précédent coûteux.

    Les deux listes se ressemblent assez pour qu'on soit tenté de n'en
    tenir qu'une. C'est exactement ce qui s'est produit avec les types
    rectificatifs et le sens débit/crédit, et chaque note de débit émise
    en était illégale. Si quelqu'un réunit celles-ci, un reçu marqué « F »
    passera de notre côté et sera refusé par le schéma de l'AT, sur un
    document déjà figé.
    """
    assert set(tipos.CODES_D_ETAT_DE_RECU) != set(
        tipos.CODES_D_ETAT_DE_FACTURATION)
    assert 'F' in tipos.CODES_D_ETAT_DE_FACTURATION
    assert 'F' not in tipos.CODES_D_ETAT_DE_RECU


def test_un_etat_de_facture_sur_un_recu_est_refuse():
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.valider_l_etat('F', 'RG')

    assert 'N, A' in str(erreur.value)


def test_un_etat_hors_enumeration_est_refuse_avant_la_signature():
    """Le troisième défaut de cette famille, et au même endroit du chemin.

    Les `choices` d'un modèle Django ne sont vérifiés qu'au `full_clean()`
    d'un formulaire. Un état arrivant par un autre chemin était signé,
    écrit dans le champ E du code QR et dans « InvoiceStatus » — où le
    schéma l'énumère. Le document s'émettait ; l'export du fichier ENTIER
    échouait.
    """
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.valider_l_etat('Z', 'FT')

    assert 'refuser l’export' in str(erreur.value)


@pytest.mark.parametrize('etat', ['N', 'S', 'A', 'R', 'F'])
def test_les_cinq_etats_de_facturation_sont_acceptes(etat):
    assert tipos.valider_l_etat(etat, 'FT') == etat


def test_un_document_porte_son_etat_jusqu_a_la_verification_du_type():
    """`verifier()` valide l'état, et pas seulement le type."""
    with pytest.raises(tipos.RegleDeType):
        tipos.verifier('FT', Decimal('80'), Decimal('98.40'), etat='Z')


# ── Le sens du mouvement ─────────────────────────────────────────────────────

def test_le_reglement_d_un_avoir_sort_l_argent():
    assert tipos.regle_au_debit('NC') is True


@pytest.mark.parametrize('type_document', ['FT', 'FS', 'FR', 'ND'])
def test_le_reglement_des_autres_documents_fait_entrer_l_argent(
        type_document):
    assert tipos.regle_au_debit(type_document) is False


def test_un_document_non_precise_fait_entrer_l_argent():
    """La seule valeur par défaut qui ne crée pas de mouvement imaginaire."""
    assert tipos.regle_au_debit(None) is False
    assert tipos.regle_au_debit('') is False


def test_un_type_de_document_inconnu_est_refuse_et_non_suppose():
    """Supposer « facture » ferait compter un remboursement en recette."""
    with pytest.raises(tipos.RegleDeType):
        tipos.regle_au_debit('ZZ')


def test_les_deux_listes_de_sens_ne_sont_pas_la_meme():
    """Elles coïncident aujourd'hui, et pour deux raisons différentes.

    `saft.TYPES_AU_DEBIT` met « NC » au débit parce qu'un avoir diminue le
    chiffre d'affaires. `tipos.TYPES_REGLES_AU_DEBIT` l'y met parce que
    l'argent SORT quand on rembourse. Les deux raisonnements se rejoignent
    sur « NC » et rien ne garantit qu'ils se rejoignent sur le type
    suivant.

    Ce test échoue si quelqu'un remplace l'une par l'autre — ce qui
    paraîtrait une simplification évidente, et c'est mot pour mot la
    confusion qui rendait illégale toute note de débit.
    """
    assert tipos.TYPES_REGLES_AU_DEBIT is not saft.TYPES_AU_DEBIT
    assert tipos.TYPES_RECTIFICATIFS != tipos.TYPES_REGLES_AU_DEBIT


# ── Ce qu'un reçu règle ──────────────────────────────────────────────────────

def test_un_recu_sans_affectation_est_refuse():
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.valider_les_affectations([])

    assert 'SourceDocumentID' in str(erreur.value)


@pytest.mark.parametrize('renvoi', ['', '   ', None])
def test_une_affectation_sans_document_est_refusee(renvoi):
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.valider_les_affectations(_affectation(document=renvoi))

    assert 'OriginatingON' in str(erreur.value)


def test_un_numero_de_document_trop_long_est_refuse_avant_l_export():
    """`OriginatingON` est borné à 60 caractères par le schéma.

    Un numéro plus long serait figé dans le reçu et ferait refuser le
    fichier entier — sur un document que plus rien ne modifie.
    """
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.valider_les_affectations(_affectation(document='F' * 61))

    assert '60' in str(erreur.value)


def test_un_numero_de_soixante_caracteres_passe():
    affectations, _, _ = tipos.valider_les_affectations(
        _affectation(document='F' * 60))

    assert affectations[0]['document'] == 'F' * 60


@pytest.mark.parametrize('valeur', ['pas-une-date', '07/03/2026',
                                    '2026-13-01', '2026-02-30'])
def test_une_date_de_document_illisible_est_refusee(valeur):
    """Le même défaut que la date d'encaissement, au même endroit.

    Le composeur du SAF-T écrit `str(valeur)[:10]` sans rien vérifier. Une
    chaîne malformée serait donc signée, figée, et ne se découvrirait qu'à
    l'export.
    """
    with pytest.raises(tipos.RegleDeType):
        tipos.valider_les_affectations(_affectation(date=valeur))


def test_une_date_en_horodatage_est_ramenee_a_une_date():
    affectations, _, _ = tipos.valider_les_affectations(
        _affectation(date=datetime(2026, 3, 7, 14, 30)))

    assert affectations[0]['date'] == date(2026, 3, 7)


@pytest.mark.parametrize('montant', [Decimal('0'), Decimal('-10.00')])
def test_un_montant_nul_ou_negatif_est_refuse(montant):
    """Zéro n'atteste rien, et un négatif ne peut pas être imprimé.

    Le Despacho 8632/2014 (2.2.6) interdit les valeurs négatives sur les
    documents émis : c'est à un document de sens inverse qu'il revient
    d'inverser un mouvement.
    """
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.valider_les_affectations(_affectation(montant=montant))

    assert '2.2.6' in str(erreur.value)


def test_le_total_du_recu_est_la_somme_de_ses_affectations():
    _, total, _ = tipos.valider_les_affectations([
        dict(UNE_AFFECTATION, montant=Decimal('60.00')),
        dict(UNE_AFFECTATION, document='FT A/2', montant=Decimal('38.40')),
    ])

    assert total == Decimal('98.40')


def test_un_recu_qui_encaisse_et_rembourse_a_la_fois_est_refuse():
    """Il n'aurait pas de total.

    La table 4.4 tient ses sommes de contrôle séparément au débit et au
    crédit, et `GrossTotal` est un nombre unique : un reçu mixte
    s'imprimerait avec un net qui ne correspond à aucun des deux
    mouvements. Le schéma, lui, accepte les deux sens dans le même
    document.
    """
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.valider_les_affectations([
            dict(UNE_AFFECTATION, type_du_document='FT'),
            dict(UNE_AFFECTATION, document='NC A/1',
                 type_du_document='NC'),
        ])

    assert 'Émettez deux reçus' in str(erreur.value)


def test_le_sens_est_fige_sur_chaque_affectation():
    affectations, _, au_debit = tipos.valider_les_affectations(
        _affectation(document='NC A/1', type_du_document='NC'))

    assert au_debit is True
    assert affectations[0]['au_debit'] is True


# ── L'encaissement d'un reçu ─────────────────────────────────────────────────

def test_un_recu_atteste_un_paiement_comme_une_facture_recu():
    assert tipos.atteste_un_paiement('RG') is True


def test_un_recu_sans_moyen_de_paiement_est_refuse():
    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier_un_recu('RG', _affectation(), [])

    assert 'quittance' in str(erreur.value)


def test_un_seul_paiement_sans_montant_vaut_le_total_du_recu():
    """Le total n'existe qu'en un seul endroit, et c'est le point.

    Le faire porter par l'appelant l'obligerait à le connaître d'avance ;
    or il est calculé ici depuis les affectations. C'est la porte par
    laquelle un cumul tenu ailleurs entre dans une quittance.
    """
    paiements = [{'mecanisme': 'TB', 'date': date(2026, 3, 20)}]

    _, total, _, _ = tipos.verifier_un_recu('RG', _affectation(), paiements)

    assert total == Decimal('60.00')
    assert paiements[0]['montant'] == Decimal('60.00')


def test_un_encaissement_different_du_total_est_refuse():
    paiements = [{'mecanisme': 'TB', 'montant': Decimal('50.00'),
                  'date': date(2026, 3, 20)}]

    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier_un_recu('RG', _affectation(), paiements)

    assert 'inférieure' in str(erreur.value)


def test_plusieurs_moyens_de_paiement_qui_somment_au_total_passent():
    """Le modèle et le fichier en acceptent plusieurs."""
    paiements = [
        {'mecanisme': 'NU', 'montant': Decimal('20.00'),
         'date': date(2026, 3, 20)},
        {'mecanisme': 'CC', 'montant': Decimal('40.00'),
         'date': date(2026, 3, 20)},
    ]

    _, total, _, avertissements = tipos.verifier_un_recu(
        'RG', _affectation(), paiements)

    assert total == Decimal('60.00')
    assert avertissements == []


def test_un_mecanisme_hors_enumeration_est_refuse():
    paiements = [{'mecanisme': 'XX', 'montant': Decimal('60.00'),
                  'date': date(2026, 3, 20)}]

    with pytest.raises(tipos.RegleDeType) as erreur:
        tipos.verifier_un_recu('RG', _affectation(), paiements)

    assert 'quatorze' in str(erreur.value)


def test_un_recu_complet_ne_rend_aucun_avertissement():
    paiements = [{'mecanisme': 'TB', 'date': date(2026, 3, 20)}]

    affectations, total, au_debit, avertissements = tipos.verifier_un_recu(
        'RG', _affectation(), paiements)

    assert len(affectations) == 1
    assert total == Decimal('60.00')
    assert au_debit is False
    assert avertissements == []


# ── Les deux mentions imprimées ──────────────────────────────────────────────

def test_la_mention_d_un_document_non_signe_dit_emitido_et_non_processado():
    """Le Despacho emploie DEUX verbes, à deux points différents.

    2.2.2, documents signés : « Processado por programa certificado
    n.º 0000/AT ». 2.2.3, documents non signés, « nomeadamente os
    recibos » : « Emitido por programa certificado n.º 0000/AT ».

    La fonction rendait « Processado » : la mention légale imprimée au
    pied de chaque reçu aurait été celle des documents signés. Rien ne
    l'aurait signalé, et un test figeait même la faute — il comparait la
    sortie de la fonction au code de la fonction, et non au texte qu'elle
    prétend citer.
    """
    mention = assinatura.mention_sans_signature('0000')

    assert mention == 'Emitido por programa certificado n.º 0000/AT'
    assert not mention.startswith('Processado')


def test_les_deux_mentions_du_despacho_sont_distinctes():
    signature = 'A' * 172
    signee = assinatura.mention_legale(signature, '1234')
    non_signee = assinatura.mention_sans_signature('1234')

    assert 'Processado por' in signee
    assert 'Emitido por' in non_signee
    assert signee != non_signee


def test_un_recu_porte_aussi_la_mention_qu_il_n_est_pas_une_facture():
    """Despacho 1.2, et il nomme la table 4.4.

    « Quaisquer documentos que não sejam faturas ou documentos
    retificativos de fatura [...] incluindo os que devam constar nas
    tabelas 4.2, 4.3 e 4.4 do SAF-T (PT), conter a expressão "Este
    documento não serve de fatura" ». Un reçu sans elle peut être présenté
    comme une facture.
    """
    assert assinatura.MENTION_NON_FATURA == (
        'Este documento não serve de fatura')
