"""L'export réel des tables 4.2 et 4.3, et les fournisseurs qui y vont.

CE QUE `tests/test_fiscal_pt_transport_et_travail.py` NE POUVAIT PAS VOIR

Ce fichier-là compose les deux tables à partir de dictionnaires écrits à
la main, et les valide contre le XSD. La composition était juste. Mais la
LECTURE EN BASE n'existait pas : `export.rassembler` ne lisait que les
documents de facturation et les reçus, et `export.composer` passait six
jeux de données à une fonction qui en accepte huit.

Le fichier réellement produit par l'écran d'export ne portait donc aucun
document de transport ni aucun devis, alors que l'entreprise en émet. La
correspondance modèle → SAF-T n'existait que dans le fichier de tests,
c'est-à-dire à l'endroit où personne ne s'en sert.

DEUX AUTRES DÉFAUTS QUE LE BRANCHEMENT A RÉVÉLÉS

1. `MouvementFiscal.emettre` recevait `nif_acquereur`, le faisait entrer
   dans le message signé ET dans le code QR, et ne le stockait nulle
   part — le modèle n'avait pas le champ. Le document restait vérifiable,
   mais l'export ne pouvait plus déclarer son client dans `MasterFiles`.

2. `MasterFiles` n'émettait aucun `Supplier`. Or `StockMovement` place
   `CustomerID` et `SupplierID` dans un choix OBLIGATOIRE : un bon de
   livraison reçu d'un fournisseur porte un `SupplierID` qui ne renvoyait
   à rien. Le XSD ne pose aucune contrainte de clé entre les deux, donc
   notre validateur acceptait le fichier — c'est celui de l'AT qui
   vérifie l'intégrité référentielle, et qui refuse le fichier entier.
"""
from datetime import date, datetime
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from apps.core.models import Company
from apps.fiscal_pt import export, schema
from apps.fiscal_pt.models import (CleDeSignature, DocumentDeTravailFiscal,
                                   MouvementFiscal, ParametresFiscauxPT,
                                   SerieFiscale)

ESPACE = '{urn:OECD:StandardAuditFile-Tax:PT_1.04_01}'

pytestmark = pytest.mark.django_db


@pytest.fixture
def chiffrement(settings):
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-exp-mvt')


@pytest.fixture
def series(entreprise, chiffrement):
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.nif = '123456789'
    parametres.save()
    cle = CleDeSignature.creer(entreprise)

    codes = {'GT': 'LMNOPQRS', 'GR': 'TUVWXYZA', 'OR': 'BCDEFGHI'}
    return {type_document: SerieFiscale.objects.create(
                company=entreprise, type_document=type_document, nom='A',
                code_de_validation=code, cle=cle)
            for type_document, code in codes.items()}


LIGNE = {'designation': 'Cabo H07V-K 2,5mm²', 'reference': 'CAB25',
         'quantite': Decimal('120'), 'unite': 'M',
         'prix_unitaire': Decimal('1.20'), 'montant': Decimal('144.00'),
         'taux': Decimal('23'), 'code_de_taux': 'NOR'}


def _heure(*parties):
    return timezone.make_aware(datetime(*parties))


def _mouvement(series, type_mouvement='GT', **extra):
    donnees = dict(
        serie=series[type_mouvement],
        date_document=date(2026, 3, 8),
        lignes=[dict(LIGNE)],
        nif_emetteur='123456789',
        identifiant_client='C500000000',
        nif_acquereur='500000000',
        debut_transport=_heure(2026, 3, 8, 7, 30),
        fin_transport=_heure(2026, 3, 8, 9, 0),
        # LA FORME IMBRIQUÉE, qui est celle que le point de transport
        # documente : l'adresse n'est qu'une partie de `ShipFrom`, qui
        # porte aussi un entrepôt et un emplacement.
        origine_envoi={'entrepot': 'ARM1',
                       'adresse': {'adresse': 'Rua do Comércio 1',
                                   'ville': 'Leiria',
                                   'code_postal': '2400-100',
                                   'pays': 'PT'}},
        # ET LA FORME PLATE, qui est celle de l'en-tête du fichier et
        # donc celle qu'on écrit spontanément. Elle faisait s'effondrer
        # l'export entier sur un « 'str' object has no attribute 'get' »
        # remonté du fond d'`_adresse`.
        destination={'adresse': 'Estrada da Marinha 44', 'ville': 'Leiria',
                     'code_postal': '2410-050', 'pays': 'PT'},
    )
    donnees.update(extra)
    return MouvementFiscal.emettre(**donnees)


def _travail(series, **extra):
    donnees = dict(
        serie=series['OR'],
        date_document=date(2026, 3, 9),
        lignes=[dict(LIGNE, date_tva=date(2026, 3, 9))],
        nif_emetteur='123456789',
        identifiant_client='C500000000',
        nif_acquereur='500000000',
    )
    donnees.update(extra)
    return DocumentDeTravailFiscal.emettre(**donnees)


def _fichier(entreprise):
    return ET.fromstring(export.composer(entreprise, date(2026, 1, 1),
                                         date(2026, 12, 31)))


# ═══ 1. LES DEUX TABLES ARRIVENT DANS LE FICHIER ═══════════════════════════

def test_le_transport_arrive_dans_le_fichier_produit_par_l_export(
        entreprise, series):
    """LE DÉFAUT CENTRAL : la composition était juste, la lecture absente."""
    mouvement = _mouvement(series)

    racine = _fichier(entreprise)
    table = racine.find(ESPACE + 'SourceDocuments/' + ESPACE
                        + 'MovementOfGoods')

    assert table is not None, (
        'la table 4.2 est absente du fichier : `saft.py` sait la composer, '
        'mais rien ne la lit en base')
    element = table.find(ESPACE + 'StockMovement')
    assert element.find(ESPACE + 'DocumentNumber').text == mouvement.numero
    assert element.find(ESPACE + 'MovementType').text == 'GT'


def test_le_devis_arrive_dans_le_fichier_produit_par_l_export(entreprise,
                                                              series):
    travail = _travail(series)

    racine = _fichier(entreprise)
    table = racine.find(ESPACE + 'SourceDocuments/' + ESPACE
                        + 'WorkingDocuments')

    assert table is not None, 'la table 4.3 est absente du fichier'
    element = table.find(ESPACE + 'WorkDocument')
    assert element.find(ESPACE + 'DocumentNumber').text == travail.numero


def test_l_en_tete_de_la_table_4_2_compte_des_lignes_et_des_quantites(
        entreprise, series):
    """ELLE NE COMPTE PAS LA MÊME CHOSE QUE LES TROIS AUTRES.

    `NumberOfMovementLines` et `TotalQuantityIssued` — un nombre de
    LIGNES et une somme de QUANTITÉS — là où les trois autres tables
    comptent des documents et additionnent des montants.
    """
    _mouvement(series)
    _mouvement(series, lignes=[dict(LIGNE), dict(LIGNE, quantite=Decimal('5'),
                                                 montant=Decimal('6.00'))])

    racine = _fichier(entreprise)
    table = racine.find(ESPACE + 'SourceDocuments/' + ESPACE
                        + 'MovementOfGoods')

    # Trois lignes sur deux documents.
    assert table.find(ESPACE + 'NumberOfMovementLines').text == '3'
    assert (Decimal(table.find(ESPACE + 'TotalQuantityIssued').text)
            == Decimal('245'))


def test_les_quatre_tables_ensemble_restent_conformes(entreprise, series):
    """La preuve qui compte : le XSD de l'AT accepte le fichier."""
    _mouvement(series)
    _travail(series)

    octets = export.composer(entreprise, date(2026, 1, 1), date(2026, 12, 31))
    anomalies = schema.valider(octets)

    assert not anomalies, anomalies


def test_les_deux_formes_d_adresse_du_trajet_sont_servies(entreprise,
                                                          series):
    """UNE ADRESSE PLATE FAISAIT S'EFFONDRER L'EXPORT ENTIER.

    `ShipTo` et `ShipFrom` portent un identifiant de livraison, une date,
    un entrepôt, un emplacement — et une adresse, qui n'en est qu'une
    partie. La forme attendue est donc imbriquée. Mais l'adresse PLATE est
    celle qu'emploie l'en-tête du fichier, et c'est celle qu'on écrit
    spontanément : elle faisait remonter « 'str' object has no attribute
    'get' » du fond d'`_adresse`, au milieu de la composition, sans dire
    ni quel document ni lequel des deux points du trajet.

    Le décor emploie l'une pour le départ et l'autre pour l'arrivée : les
    deux doivent produire la même structure.
    """
    _mouvement(series)

    racine = _fichier(entreprise)
    element = racine.find(ESPACE + 'SourceDocuments/' + ESPACE
                          + 'MovementOfGoods/' + ESPACE + 'StockMovement')

    depart = element.find(ESPACE + 'ShipFrom/' + ESPACE + 'Address')
    arrivee = element.find(ESPACE + 'ShipTo/' + ESPACE + 'Address')

    assert depart.find(ESPACE + 'City').text == 'Leiria'
    assert depart.find(ESPACE + 'PostalCode').text == '2400-100'
    assert arrivee.find(ESPACE + 'City').text == 'Leiria'
    assert arrivee.find(ESPACE + 'PostalCode').text == '2410-050'

    # Et ce que la forme plate ne peut pas porter reste disponible dans
    # l'autre : l'entrepôt du départ.
    assert (element.find(ESPACE + 'ShipFrom/' + ESPACE + 'WarehouseID').text
            == 'ARM1')


def test_une_adresse_de_trajet_qui_n_en_est_pas_une_est_nommee():
    """Le refus dit QUEL point du trajet, et ce qui était attendu.

    Un `AttributeError` remonté d'`_adresse` ne dit ni l'un ni l'autre, et
    il arrive au milieu de la composition d'un fichier de plusieurs mois.
    """
    from apps.fiscal_pt import saft

    with pytest.raises(saft.ErreurSAFT) as refus:
        saft.point_de_transport('ShipTo', {'adresse': ['Rua X', 'Leiria']})

    message = str(refus.value)
    assert 'ShipTo' in message
    assert 'code_postal' in message


# ═══ 2. LE RÉFÉRENTIEL QUE LES DEUX TABLES ENRICHISSENT ════════════════════

def test_le_produit_transporte_est_declare_dans_le_referentiel(entreprise,
                                                               series):
    """Un `ProductCode` qu'aucune table ne déclare fait refuser le fichier,
    et le validateur ne dit pas lequel des quatre blocs l'a employé."""
    _mouvement(series)

    racine = _fichier(entreprise)
    codes = [p.find(ESPACE + 'ProductCode').text
             for p in racine.iter(ESPACE + 'Product')]

    assert 'CAB25' in codes


def test_le_taux_du_transport_est_declare_dans_la_table_des_taux(entreprise,
                                                                 series):
    _mouvement(series)

    racine = _fichier(entreprise)
    entrees = list(racine.iter(ESPACE + 'TaxTableEntry'))

    assert any(e.find(ESPACE + 'TaxCode').text == 'NOR' for e in entrees)


def test_le_client_du_transport_est_declare_avec_son_nif(entreprise, series):
    """LE CHAMP QUI N'ÉTAIT PAS STOCKÉ.

    `emettre` recevait `nif_acquereur`, le faisait entrer dans le message
    signé et dans le code QR, et ne le gardait nulle part. Sans lui,
    l'export ne peut pas déclarer le client — et un `CustomerID` qui
    désigne un client non déclaré fait refuser le fichier entier.
    """
    mouvement = _mouvement(series)
    assert mouvement.nif_acquereur == '500000000'

    racine = _fichier(entreprise)
    clients = {c.find(ESPACE + 'CustomerID').text:
               c.find(ESPACE + 'CustomerTaxID').text
               for c in racine.iter(ESPACE + 'Customer')}

    assert clients.get('C500000000') == '500000000'


# ═══ 3. LE FOURNISSEUR, QUI N'AVAIT PAS DE TABLE ═══════════════════════════

def test_un_mouvement_de_fournisseur_declare_son_fournisseur(entreprise,
                                                             series):
    """`MasterFiles` N'ÉMETTAIT AUCUN `Supplier`.

    `StockMovement` place `CustomerID` et `SupplierID` dans un choix
    obligatoire : un bon de livraison reçu d'un fournisseur porte un
    `SupplierID`, qui ne renvoyait à rien.

    Le XSD ne pose aucune contrainte de clé entre les deux : notre
    validateur acceptait le fichier. C'est celui de l'AT qui vérifie
    l'intégrité référentielle, et il refuse le fichier ENTIER — sur des
    mois de documents déjà remis.
    """
    _mouvement(series, type_mouvement='GR', identifiant_client='',
               identifiant_fournisseur='F500111222',
               nif_acquereur='500111222')

    racine = _fichier(entreprise)
    fournisseurs = {f.find(ESPACE + 'SupplierID').text:
                    f.find(ESPACE + 'SupplierTaxID').text
                    for f in racine.iter(ESPACE + 'Supplier')}

    assert fournisseurs, 'aucun Supplier dans MasterFiles'
    assert fournisseurs.get('F500111222') == '500111222'


def test_le_fournisseur_n_est_pas_declare_parmi_les_clients(entreprise,
                                                            series):
    """Deux tables distinctes, et un `SupplierID` ne se résout pas dans la
    table des clients."""
    _mouvement(series, type_mouvement='GR', identifiant_client='',
               identifiant_fournisseur='F500111222',
               nif_acquereur='500111222')

    racine = _fichier(entreprise)
    identifiants = [c.find(ESPACE + 'CustomerID').text
                    for c in racine.iter(ESPACE + 'Customer')]

    assert 'F500111222' not in identifiants


def test_masterfiles_range_les_fournisseurs_entre_clients_et_produits(
        entreprise, series):
    """L'ORDRE DE `MasterFiles` EST IMPOSÉ : Customer, Supplier, Product,
    TaxTable. Les ajouter à la fin, où c'est plus simple, donnerait un
    fichier dont le contenu est juste et que le schéma refuse en entier.
    """
    _mouvement(series)
    _mouvement(series, type_mouvement='GR', identifiant_client='',
               identifiant_fournisseur='F500111222',
               nif_acquereur='500111222')

    racine = _fichier(entreprise)
    referentiels = racine.find(ESPACE + 'MasterFiles')
    noms = [enfant.tag.replace(ESPACE, '') for enfant in referentiels]

    assert noms.index('Supplier') > noms.index('Customer')
    assert noms.index('Supplier') < noms.index('Product')


def test_un_fichier_avec_fournisseur_reste_conforme(entreprise, series):
    _mouvement(series, type_mouvement='GR', identifiant_client='',
               identifiant_fournisseur='F500111222',
               nif_acquereur='500111222')

    octets = export.composer(entreprise, date(2026, 1, 1), date(2026, 12, 31))
    anomalies = schema.valider(octets)

    assert not anomalies, anomalies


# ═══ 4. CE QUE L'ANNULATION DONNE DANS CES DEUX TABLES ═════════════════════

def test_un_transport_annule_porte_son_motif_et_sa_date(entreprise, series):
    """Les quatre `*StatusDate` recevaient l'horodatage d'ÉMISSION : le
    défaut était dans les quatre tables, et se corrige dans les quatre."""
    mouvement = _mouvement(series)
    annule_le = _heure(2026, 3, 14, 11, 20, 5)
    mouvement.annuler('Transport interrompu, retour au dépôt',
                      quand=annule_le)

    racine = _fichier(entreprise)
    etat = racine.find(ESPACE + 'SourceDocuments/' + ESPACE
                       + 'MovementOfGoods/' + ESPACE + 'StockMovement/'
                       + ESPACE + 'DocumentStatus')

    from datetime import timezone as dt_timezone

    assert etat.find(ESPACE + 'MovementStatus').text == 'A'
    assert (etat.find(ESPACE + 'Reason').text
            == 'Transport interrompu, retour au dépôt')

    # LA DATE DE L'ÉTAT, ET NON CELLE DE L'ÉMISSION. Le fichier déclare
    # l'heure UTC, comme la chaîne signée : 11:20:05 à Paris s'y écrit
    # 10:20:05, et les deux coïncident — l'administration retombe donc
    # bien sur notre signature.
    attendue = annule_le.astimezone(dt_timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S')
    assert etat.find(ESPACE + 'MovementStatusDate').text == attendue

    mouvement.refresh_from_db()
    assert mouvement.horodatage.astimezone(dt_timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S') != attendue


def test_un_devis_annule_porte_son_motif(entreprise, series):
    travail = _travail(series)
    travail.annuler('Devis refusé par le client')

    racine = _fichier(entreprise)
    etat = racine.find(ESPACE + 'SourceDocuments/' + ESPACE
                       + 'WorkingDocuments/' + ESPACE + 'WorkDocument/'
                       + ESPACE + 'DocumentStatus')

    assert etat.find(ESPACE + 'WorkStatus').text == 'A'
    assert etat.find(ESPACE + 'Reason').text == 'Devis refusé par le client'
