# -*- coding: utf-8 -*-
"""Les tables 4.2 et 4.3 du SAF-T : transport et documents de travail.

POURQUOI CES DEUX TABLES ÉTAIENT EXIGÉES ICI

L'entreprise transporte des marchandises — ses propres matériaux vers ses
chantiers — et remet des devis à ses clients. La table 4.2
(`MovementOfGoods`) porte les guias de transporte et de remessa ; la 4.3
(`WorkingDocuments`) porte les devis, fiches de chantier et bons de
commande. Ni l'une ni l'autre n'était produite : un fichier remis à l'AT
déclarait donc une activité sans ses documents de circulation.

QUATRE LISTES D'ÉTATS, ET ELLES NE SE RESSEMBLENT QUE DE LOIN

    InvoiceStatus   (4.1)  N  S  A  R  F
    MovementStatus  (4.2)  N  T  A  F  R
    WorkStatus      (4.3)  N  A  F
    PaymentStatus   (4.4)  N  A

Le « T » de la table 4.2 — biens en cours d'acheminement — n'existe dans
aucune autre. Tenir une seule liste ferait passer de notre côté un état que
le schéma refuse, sur un document déjà signé, et bloquerait le fichier
entier. C'est le même piège que les deux listes de types rectificatifs, à
deux endroits de plus.

ET L'EN-TÊTE DE LA TABLE 4.2 NE COMPTE PAS LA MÊME CHOSE QUE LES AUTRES :
`NumberOfMovementLines` et `TotalQuantityIssued` — un nombre de LIGNES et
une somme de QUANTITÉS — là où les trois autres comptent des documents et
additionnent des montants. Recopier l'en-tête voisin donnerait un fichier
dont deux nombres seulement diffèrent, et qui serait refusé en entier.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError

from apps.core.models import Company
from apps.fiscal_pt import saft, schema, tipos
from apps.fiscal_pt.models import (CleDeSignature, DocumentDeTravailFiscal,
                                   MouvementFiscal, ParametresFiscauxPT,
                                   SerieFiscale)

pytestmark = pytest.mark.django_db


@pytest.fixture
def chiffrement(settings):
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-gt')


@pytest.fixture
def series(entreprise, chiffrement):
    """Une série par type employé ici."""
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.nif = '123456789'
    parametres.save()
    cle = CleDeSignature.creer(entreprise)

    codes = {'GT': 'JFFNVTC7', 'GR': 'CSDF7T5H', 'GD': 'RQD8L6DG',
             'OR': 'KSMLFPQZ', 'FO': 'LMNOPQRS'}
    return {type_document: SerieFiscale.objects.create(
                company=entreprise, type_document=type_document, nom='A',
                code_de_validation=code, cle=cle)
            for type_document, code in codes.items()}


LIGNE_MVT = {
    'designation': 'Cabo H07V-U 2,5 mm²', 'reference': 'CAB25',
    'quantite': Decimal('120'), 'unite': 'M',
    'prix_unitaire': Decimal('1.20'), 'taux': Decimal('23'),
    'code_de_taux': 'NOR',
}

LIGNE_TRV = {
    'designation': 'Instalação elétrica complète', 'reference': 'INST',
    'quantite': Decimal('1'), 'unite': 'UN',
    'prix_unitaire': Decimal('2500.00'), 'taux': Decimal('23'),
    'code_de_taux': 'NOR',
}

TRAJET_DEPART = {'adresse': {'adresse': 'Armazém 1', 'ville': 'Leiria',
                             'code_postal': '2400-000', 'pays': 'PT'}}
TRAJET_ARRIVEE = {'adresse': {'adresse': 'Obra Rua X', 'ville': 'Pombal',
                              'code_postal': '3100-000', 'pays': 'PT'}}


def _heure(*parties):
    """Une heure AVEC fuseau.

    Le decor en passait sans, et Django ne faisait qu'avertir. Or
    `MovementStartTime` part dans le SAF-T et compte legalement : une
    heure naive se decalerait d'une a deux heures selon le reglage du
    serveur, sur un document deja signe. `emettre` la refuse desormais, et
    ce decor doit donc dire l'heure entierement.
    """
    from django.utils import timezone

    return timezone.make_aware(datetime(*parties))


def _mouvement(series, type_mouvement='GT', **extra):
    donnees = dict(
        serie=series[type_mouvement],
        date_document=date(2026, 3, 8),
        lignes=[dict(LIGNE_MVT)],
        nif_emetteur='123456789',
        identifiant_client='C1',
        debut_transport=_heure(2026, 3, 8, 7, 30),
        fin_transport=_heure(2026, 3, 8, 9, 0),
        origine_envoi=TRAJET_DEPART,
        destination=TRAJET_ARRIVEE,
    )
    donnees.update(extra)
    return MouvementFiscal.emettre(**donnees)


def _travail(series, type_travail='OR', **extra):
    donnees = dict(
        serie=series[type_travail],
        date_document=date(2026, 3, 9),
        lignes=[dict(LIGNE_TRV)],
        nif_emetteur='123456789',
        identifiant_client='C1',
    )
    donnees.update(extra)
    return DocumentDeTravailFiscal.emettre(**donnees)


# ═══ 1. L'ÉMISSION ══════════════════════════════════════════════════════════

def test_un_mouvement_est_numerote_signe_et_horodate(series):
    mouvement = _mouvement(series)

    assert mouvement.numero == 'GT A/1'
    assert mouvement.atcud.startswith('JFFNVTC7-')
    assert mouvement.atcud.endswith('-1')
    assert len(mouvement.signature) > 100
    assert mouvement.total == Decimal('144.00')


def test_un_document_de_travail_est_numerote_et_signe(series):
    document = _travail(series)

    assert document.numero == 'OR A/1'
    assert document.atcud.startswith('KSMLFPQZ-')
    assert len(document.signature) > 100
    assert document.total == Decimal('2500.00')


def test_la_chaine_relie_les_documents_d_une_serie(series):
    """La signature de chacun porte celle du précédent.

    C'est la garantie que personne n'a inséré ni retiré un document : le
    SAF-T permet à l'AT de recalculer la chaîne entière.
    """
    premier = _mouvement(series)
    second = _mouvement(series)

    assert premier.signature_precedente == ''
    assert second.signature_precedente == premier.signature
    assert second.numero_sequentiel == premier.numero_sequentiel + 1


def test_un_document_emis_ne_se_modifie_pas(series):
    mouvement = _mouvement(series)
    mouvement.commentaire = 'autre chose'

    with pytest.raises(ValidationError):
        mouvement.save()


def test_un_document_emis_ne_se_supprime_pas(series):
    """La série ne doit sauter aucun numéro : on annule, on ne supprime pas."""
    document = _travail(series)

    with pytest.raises(ValidationError):
        document.delete()


# ═══ 2. LE CHOIX CLIENT OU FOURNISSEUR, PROPRE À LA TABLE 4.2 ══════════════

def test_un_mouvement_sans_client_ni_fournisseur_est_refuse(series):
    """`xs:choice` OBLIGATOIRE : exactement l'un des deux.

    Notre validateur de schéma accepte les deux cas — il lit le modèle de
    contenu, pas le choix — et celui de l'AT refuse. Le contrôle doit donc
    être posé AVANT la signature.
    """
    with pytest.raises(ValidationError) as refus:
        _mouvement(series, identifiant_client='')

    assert 'un des deux' in str(refus.value)


def test_un_mouvement_avec_les_deux_est_refuse(series):
    with pytest.raises(ValidationError) as refus:
        _mouvement(series, identifiant_fournisseur='F1')

    assert 'Les deux' in str(refus.value)


def test_un_mouvement_depuis_un_fournisseur_est_accepte(series):
    """Une réception porte le fournisseur, pas le client."""
    mouvement = _mouvement(series, type_mouvement='GR',
                           identifiant_client='',
                           identifiant_fournisseur='F1')

    assert mouvement.identifiant_fournisseur == 'F1'
    assert mouvement.identifiant_client == ''


# ═══ 3. LES ÉTATS, QUATRE LISTES DISTINCTES ════════════════════════════════

def test_l_etat_de_transit_n_existe_que_pour_un_mouvement(series):
    """« T » est accepté par la table 4.2 et par elle seule."""
    mouvement = _mouvement(series, etat='T')
    assert mouvement.etat == 'T'

    with pytest.raises(ValidationError):
        _travail(series, etat='T')


def test_un_document_de_travail_refuse_les_etats_de_facture(series):
    """« S » et « R » n'existent pas dans `WorkStatus`."""
    for etat in ('S', 'R'):
        with pytest.raises(ValidationError):
            _travail(series, etat=etat)


def test_les_quatre_listes_d_etats_sont_distinctes():
    """La garde qui empêche de les réunir.

    Elles se ressemblent assez pour qu'on soit tenté de n'en tenir qu'une.
    Le « T » de la table 4.2 et l'absence de « S » dans la 4.3 le
    rendraient faux dans les deux sens.
    """
    facturation = set(tipos.CODES_D_ETAT_DE_FACTURATION)
    mouvement = set(tipos.CODES_D_ETAT_DE_MOUVEMENT)
    travail = set(tipos.CODES_D_ETAT_DE_TRAVAIL)
    recu = set(tipos.CODES_D_ETAT_DE_RECU)

    assert len({frozenset(facturation), frozenset(mouvement),
                frozenset(travail), frozenset(recu)}) == 4
    assert 'T' in mouvement and 'T' not in facturation
    assert 'S' in facturation and 'S' not in mouvement


def test_les_trois_listes_de_sens_ne_sont_pas_la_meme():
    """Trois raisons différentes de mettre une ligne au débit.

    `saft.TYPES_AU_DEBIT` d'après l'effet sur le chiffre d'affaires,
    `tipos.TYPES_REGLES_AU_DEBIT` d'après le sens de l'argent,
    `tipos.MOUVEMENTS_AU_DEBIT` d'après le sens de la marchandise. Les
    deux premières coïncident sur « NC » par accident.
    """
    assert tipos.MOUVEMENTS_AU_DEBIT is not saft.TYPES_AU_DEBIT
    assert tipos.MOUVEMENTS_AU_DEBIT is not tipos.TYPES_REGLES_AU_DEBIT
    assert set(tipos.MOUVEMENTS_AU_DEBIT) != set(saft.TYPES_AU_DEBIT)


# ═══ 4. LES LIGNES ══════════════════════════════════════════════════════════

def test_un_document_sans_ligne_est_refuse_avant_la_signature(series):
    """Le schéma écrit « Line+ ».

    Sans ce contrôle, le document se signerait et l'export du fichier
    ENTIER échouerait — sur un document que plus rien ne modifie. C'est
    le défaut qu'`InvoiceLine` avait déjà posé une fois.
    """
    with pytest.raises(ValidationError) as refus:
        _mouvement(series, lignes=[])

    assert 'Line+' in str(refus.value)


def test_une_quantite_negative_est_refusee(series):
    """Despacho 8632/2014, point 2.2.6 : pas de valeur négative."""
    ligne = dict(LIGNE_MVT, quantite=Decimal('-5'))

    with pytest.raises(ValidationError) as refus:
        _mouvement(series, lignes=[ligne])

    assert '2.2.6' in str(refus.value)


def test_le_montant_se_calcule_a_defaut(series):
    """120 × 1,20 = 144,00, sans que l'appelant ait à le dire."""
    mouvement = _mouvement(series)
    assert mouvement.lignes[0]['montant'] == '144.00'


# ═══ 5. LE SAF-T ════════════════════════════════════════════════════════════

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
PRODUITS = [{'code': 'CAB25', 'description': 'Cabo'}]
TAUX = [('NOR', Decimal('23'), 'PT')]


def _donnees_de_mouvement(mouvement):
    return {
        'numero': mouvement.numero, 'atcud': mouvement.atcud,
        'signature': mouvement.signature,
        'version_cle': mouvement.version_cle,
        'date': mouvement.date_document,
        'type_mouvement': mouvement.type_mouvement,
        'etat': mouvement.etat, 'horodatage': mouvement.horodatage,
        'emetteur': 'Orion', 'client': mouvement.identifiant_client or None,
        'fournisseur': mouvement.identifiant_fournisseur or None,
        'debut_transport': mouvement.debut_transport,
        'fin_transport': mouvement.fin_transport,
        'origine_envoi': mouvement.origine_envoi,
        'destination': mouvement.destination,
        'lignes': [dict(l, quantite=Decimal(l['quantite']),
                        prix_unitaire=Decimal(l['prix_unitaire']),
                        montant=Decimal(l['montant']),
                        taux=Decimal(l['taux']))
                   for l in mouvement.lignes],
        'total_base': mouvement.total_base,
        'total_taxes': mouvement.total_taxes, 'total': mouvement.total,
    }


def _donnees_de_travail(document):
    return {
        'numero': document.numero, 'atcud': document.atcud,
        'signature': document.signature,
        'version_cle': document.version_cle,
        'date': document.date_document,
        'type_travail': document.type_travail,
        'etat': document.etat, 'horodatage': document.horodatage,
        'emetteur': 'Orion', 'client': document.identifiant_client,
        'lignes': [dict(l, quantite=Decimal(l['quantite']),
                        prix_unitaire=Decimal(l['prix_unitaire']),
                        montant=Decimal(l['montant']),
                        taux=Decimal(l['taux']),
                        date_tva=document.date_document)
                   for l in document.lignes],
        'total_base': document.total_base,
        'total_taxes': document.total_taxes, 'total': document.total,
    }


def test_le_fichier_aux_quatre_tables_est_conforme(series):
    """La preuve qui compte : le schéma de l'AT accepte le fichier."""
    from xml.etree import ElementTree as ET

    mouvement = _mouvement(series)
    document = _travail(series)

    octets = saft.composer(
        ENTETE, CLIENTS, PRODUITS, TAUX, [],
        mouvements=[_donnees_de_mouvement(mouvement)],
        travaux=[_donnees_de_travail(document)])
    racine = ET.fromstring(octets)

    assert schema.valider(racine) == []


def test_les_tables_viennent_dans_l_ordre_du_schema(series):
    """`SourceDocuments` impose la suite, et l'intervertir fait tout refuser."""
    from xml.etree import ElementTree as ET

    octets = saft.composer(
        ENTETE, CLIENTS, PRODUITS, TAUX, [],
        mouvements=[_donnees_de_mouvement(_mouvement(series))],
        travaux=[_donnees_de_travail(_travail(series))])
    racine = ET.fromstring(octets)

    espace = '{%s}' % saft.ESPACE_DE_NOMS
    sources = racine.find(espace + 'SourceDocuments')
    noms = [enfant.tag.replace(espace, '') for enfant in sources]

    # On verifie l'ORDRE RELATIF et non la liste exacte : « SalesInvoices »
    # est toujours declaree, meme vide -- une periode sans vente est une
    # information, contrairement a une famille de documents absente du
    # logiciel. Figer la liste entiere ferait echouer ce test le jour ou
    # une cinquieme table serait produite, sans qu'aucun ordre n'ait change.
    attendu = ['SalesInvoices', 'MovementOfGoods', 'WorkingDocuments',
               'Payments']
    rangs = [attendu.index(nom) for nom in noms if nom in attendu]
    assert rangs == sorted(rangs), (
        'les tables ne viennent pas dans l-ordre de SourceDocuments : %s'
        % noms)
    assert 'MovementOfGoods' in noms and 'WorkingDocuments' in noms
    assert noms.index('MovementOfGoods') < noms.index('WorkingDocuments')


def test_l_en_tete_de_la_table_4_2_compte_des_lignes_et_des_quantites(series):
    """ELLE NE COMPTE PAS LA MÊME CHOSE QUE LES TROIS AUTRES.

    `NumberOfMovementLines` et `TotalQuantityIssued`, et non
    `NumberOfEntries`, `TotalDebit`, `TotalCredit`. Deux mouvements de 120
    mètres donnent deux lignes et 240 — pas deux documents et un montant.
    """
    from xml.etree import ElementTree as ET

    premier = _mouvement(series)
    second = _mouvement(series)

    octets = saft.composer(
        ENTETE, CLIENTS, PRODUITS, TAUX, [],
        mouvements=[_donnees_de_mouvement(premier),
                    _donnees_de_mouvement(second)])
    racine = ET.fromstring(octets)
    espace = '{%s}' % saft.ESPACE_DE_NOMS
    table = racine.find(espace + 'SourceDocuments/' + espace
                        + 'MovementOfGoods')

    assert table.find(espace + 'NumberOfMovementLines').text == '2'
    # On compare la VALEUR et non la chaine : `_quantite` ne garde pas les
    # zeros de queue, et figer « 240.00000 » ferait echouer ce test sur un
    # detail de mise en forme plutot que sur la propriete mesuree.
    assert Decimal(
        table.find(espace + 'TotalQuantityIssued').text) == Decimal('240')
    assert table.find(espace + 'NumberOfEntries') is None


def test_un_mouvement_annule_est_compte_mais_sa_quantite_ne_l_est_pas(series):
    """Même règle que pour les autres tables, et même raison.

    L'annulé reste dans le fichier — la série ne doit sauter aucun numéro —
    et son contenu ne compte plus dans les totaux.
    """
    from xml.etree import ElementTree as ET

    vivant = _mouvement(series)
    annule = _mouvement(series, etat='A')

    octets = saft.composer(
        ENTETE, CLIENTS, PRODUITS, TAUX, [],
        mouvements=[_donnees_de_mouvement(vivant),
                    _donnees_de_mouvement(annule)])
    racine = ET.fromstring(octets)
    espace = '{%s}' % saft.ESPACE_DE_NOMS
    table = racine.find(espace + 'SourceDocuments/' + espace
                        + 'MovementOfGoods')

    assert table.find(espace + 'NumberOfMovementLines').text == '2'
    assert Decimal(
        table.find(espace + 'TotalQuantityIssued').text) == Decimal('120')


def test_le_trajet_figure_dans_le_fichier(series):
    """Pour une guia de transporte, c'est l'information même du document."""
    from xml.etree import ElementTree as ET

    octets = saft.composer(
        ENTETE, CLIENTS, PRODUITS, TAUX, [],
        mouvements=[_donnees_de_mouvement(_mouvement(series))])
    texte = octets.decode('utf-8')

    assert 'ShipFrom' in texte and 'ShipTo' in texte
    assert 'Leiria' in texte and 'Pombal' in texte
    # La fin AVANT le début : l'ordre du schéma, qui surprend.
    assert texte.index('MovementEndTime') < texte.index('MovementStartTime')


def test_un_mouvement_est_signe_contrairement_a_un_recu(series):
    """`Hash` et `HashControl` sont présents dans la table 4.2.

    La table 4.4 ne les a pas : un reçu n'est pas signé. Les deux tables
    sont voisines et leurs règles de signature s'opposent.
    """
    from xml.etree import ElementTree as ET

    octets = saft.composer(
        ENTETE, CLIENTS, PRODUITS, TAUX, [],
        mouvements=[_donnees_de_mouvement(_mouvement(series))])
    texte = octets.decode('utf-8')

    assert '<Hash>' in texte
    assert '<HashControl>' in texte


# ═══ 6. LES MENTIONS IMPRIMÉES ══════════════════════════════════════════════

def test_un_mouvement_porte_les_deux_mentions(series):
    """Signé, donc « Processado » — et table 4.2, donc la seconde mention.

    Le Despacho 8632/2014 nomme explicitement les tables 4.2, 4.3 et 4.4
    au point 1.2 : tout document de ces tables présentable au client doit
    porter « Este documento não serve de fatura ».
    """
    mouvement = _mouvement(series)
    mentions = mouvement.mentions_legales('1234')

    assert any('Processado por programa certificado n.º 1234/AT' in m
               for m in mentions)
    assert 'Este documento não serve de fatura' in mentions


def test_un_devis_porte_les_deux_mentions(series):
    """Un devis qui ne porte pas la seconde peut être pris pour une facture."""
    document = _travail(series)
    mentions = document.mentions_legales('1234')

    assert any('Processado' in m for m in mentions)
    assert 'Este documento não serve de fatura' in mentions


# ═══ 7. LE CODE QR ══════════════════════════════════════════════════════════

def test_le_code_qr_porte_le_type_et_l_espace_fiscal(series):
    """L'ESPACE FISCAL N'EST PAS « 0 » ICI, contrairement au reçu.

    Les spécifications réservent « I1:0 » au document « sem indicação da
    taxa de IVA, que deva constar na tabela 4.2, 4.3 ou 4.4 ». La
    condition est l'ABSENCE de taux, pas l'appartenance à ces tables : un
    reçu n'indique aucun taux, un mouvement porte un bloc `Tax` par ligne.
    Recopier la règle du reçu déclarerait l'inverse du fichier.
    """
    mouvement = _mouvement(series)

    assert 'D:GT' in mouvement.contenu_qr
    assert 'I1:0*' not in mouvement.contenu_qr
    assert 'I1:PT' in mouvement.contenu_qr


def test_les_quatre_caracteres_du_qr_viennent_de_la_signature(series):
    """Champ Q : « 4 carateres do Hash », et ce sont les bons."""
    from apps.fiscal_pt import assinatura

    document = _travail(series)
    attendus = assinatura.caracteres_imprimes(document.signature)

    assert f'Q:{attendus}' in document.contenu_qr


def test_une_heure_de_transport_sans_fuseau_est_refusee(series):
    """Elle se decalerait d'une a deux heures, en silence.

    Django n'AVERTIT que : il enregistre la valeur et la journalise comme
    « naive datetime ... while time zone support is active ». L'heure
    declaree dans le SAF-T pourrait donc differer de l'heure reelle du
    depart, sur un document signe, et la loi veut ce document emis AVANT
    le depart.

    Meme defaut que les sauvegardes planifiees, dont l'heure etait
    interpretee en UTC quand l'ecran annoncait l'heure locale. Ici on
    refuse plutot que de deviner.
    """
    with pytest.raises(ValidationError) as refus:
        _mouvement(series, debut_transport=datetime(2026, 3, 8, 7, 30))

    assert 'fuseau' in str(refus.value)


def test_une_fin_de_transport_sans_fuseau_est_refusee_aussi(series):
    with pytest.raises(ValidationError):
        _mouvement(series, fin_transport=datetime(2026, 3, 8, 9, 0))
