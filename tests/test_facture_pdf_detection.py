"""Extraction des informations d'une facture fournisseur en PDF.

**Rien n'est jamais enregistré par la détection.** Une facture crée une
dette et part en comptabilité : un import qui enregistrerait directement ce
qu'il croit avoir lu transformerait une erreur d'extraction en écriture
comptable, et personne ne s'en apercevrait avant le rapprochement
bancaire. L'extraction propose, un humain valide.

Deux contrôles font la différence entre « fiable » et « plausible », et
c'est eux que ce fichier vérifie le plus :

**HT + TVA = TTC.** Trois montants qui ne se réconcilient pas prouvent
qu'au moins un est faux. On ne sait pas lequel — donc on ne « corrige »
rien, on le dit. Quand il n'en manque qu'un, il est déduit : une
soustraction est sûre, une case vide se remplit à la main et de travers.

**Les clés de contrôle du SIRET et du numéro de TVA.** Un SIRET vérifie
Luhn ; une TVA française porte une clé calculable depuis le SIREN. Sans ces
contrôles, un numéro de commande à 14 chiffres passerait pour un SIRET et
rattacherait la facture au mauvais fournisseur — en silence, et la dette
d'un autre se retrouverait à payer.

Les PDF de test sont **générés** par reportlab, pas simulés : c'est le même
chemin qu'une vraie facture (texte posé dans un flux PDF, relu par pypdf),
avec ses aléas d'extraction. Tester sur des chaînes de caractères aurait
prouvé que les expressions régulières fonctionnent, pas que la lecture
d'un PDF fonctionne.
"""

import io
from datetime import date
from decimal import Decimal

import pytest

from apps.purchases.invoice_detection import (
    FactureIllisible,
    chercher_fournisseur,
    chercher_numero,
    chercher_numero_tva,
    chercher_siret,
    cle_tva_francaise,
    dates_du_texte,
    detecter_facture,
    extraire_texte,
    luhn_valide,
    reconcilier,
    taux_du_texte,
)


# ── Terrain : de vrais PDF ──────────────────────────────────────────────────

def pdf_de(lignes):
    """Un PDF d'une page portant ces lignes. Rend les octets.

    reportlab écrit, pypdf relit : le même chemin qu'une facture réelle.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=A4)
    feuille.setFont('Helvetica', 10)
    y = 800
    for ligne in lignes:
        feuille.drawString(40, y, ligne)
        y -= 14
    feuille.showPage()
    feuille.save()
    return tampon.getvalue()


# SIRET valide au sens de Luhn (celui de la DGFiP, public).
SIRET_VALIDE = '40483304800022'
# SIREN dont on calcule la clé pour obtenir une TVA valide.
SIREN = '404833048'
TVA_VALIDE = f'FR{cle_tva_francaise(SIREN):02d}{SIREN}'


FACTURE_SIMPLE = [
    'MATERIAUX DU NORD SAS',
    f'SIRET : {SIRET_VALIDE}',
    f'TVA intracommunautaire : {TVA_VALIDE}',
    '',
    'FACTURE N° FA-2026-0147',
    'Date de facture : 12/03/2026',
    "Date d'échéance : 11/04/2026",
    '',
    'Ciment CEM II 35 kg      20      6,40      128,00',
    'Sable 0/4 en vrac         3     32,50       97,50',
    '',
    'Total HT          225,50',
    'TVA 20 %           45,10',
    'Total TTC         270,60',
]


# ── 1. Lecture du PDF ───────────────────────────────────────────────────────

def test_le_texte_est_extrait_d_un_vrai_pdf():
    texte, pages = extraire_texte(pdf_de(FACTURE_SIMPLE))
    assert pages == 1
    assert 'FA-2026-0147' in texte


def test_un_pdf_sans_texte_est_explique_et_non_vide(monkeypatch):
    """Un scan ne contient qu'une image : aucune expression régulière n'y
    changera rien.

    « Rien trouvé » sans raison n'aide personne. Le message doit mener à
    une action : demander le PDF d'origine.
    """
    from apps.purchases import invoice_detection

    monkeypatch.setattr(invoice_detection, 'extraire_texte',
                        lambda octets: ('   \n  ', 3))
    resultat = invoice_detection.detecter_facture(b'%PDF-1.4')
    assert resultat['texte_trouve'] is False
    assert resultat['pages'] == 3
    assert 'scanné' in resultat['message'] or 'image' in resultat['message']
    assert resultat['champs'] == {}


def test_un_fichier_qui_n_est_pas_un_pdf_est_refuse_proprement():
    with pytest.raises(FactureIllisible):
        extraire_texte(b'ceci est un fichier texte, pas un PDF')


# ── 2. Les clés de contrôle ─────────────────────────────────────────────────

@pytest.mark.parametrize('chiffres,attendu', [
    (SIRET_VALIDE, True),
    ('40483304800023', False),      # dernier chiffre changé
    ('12345678901234', False),
    ('', False),
    ('abcdefghijklmn', False),
])
def test_luhn(chiffres, attendu):
    assert luhn_valide(chiffres) is attendu


def test_le_siret_est_trouve_et_valide():
    assert chercher_siret(f'SIRET {SIRET_VALIDE} fin') == SIRET_VALIDE


def test_un_faux_siret_n_est_pas_retenu():
    """LE contrôle qui évite de rattacher la facture au mauvais fournisseur.

    Sans Luhn, n'importe quel numéro de commande à 14 chiffres passerait —
    une erreur silencieuse, et qui se propage en comptabilité.
    """
    assert chercher_siret('Commande n° 12345678901234') is None


def test_le_siret_est_lu_malgre_les_espaces():
    espace = f'{SIRET_VALIDE[:3]} {SIRET_VALIDE[3:6]} {SIRET_VALIDE[6:9]} {SIRET_VALIDE[9:]}'
    assert chercher_siret(f'SIRET : {espace}') == SIRET_VALIDE


def test_la_cle_de_tva_est_celle_de_la_formule():
    """clé = (12 + 3·(SIREN mod 97)) mod 97."""
    attendu = (12 + 3 * (int(SIREN) % 97)) % 97
    assert cle_tva_francaise(SIREN) == attendu


def test_le_numero_de_tva_est_trouve_et_verifie():
    assert chercher_numero_tva(f'TVA {TVA_VALIDE}') == TVA_VALIDE


def test_un_numero_de_tva_a_cle_fausse_est_rejete():
    """Une clé qui ne tombe pas juste est une faute de lecture, pas une TVA."""
    fausse = (cle_tva_francaise(SIREN) + 1) % 97
    assert chercher_numero_tva(f'TVA FR{fausse:02d}{SIREN}') is None


# ── 3. Numéro de facture ────────────────────────────────────────────────────

@pytest.mark.parametrize('texte,attendu', [
    ('FACTURE N° FA-2026-0147', 'FA-2026-0147'),
    ('Facture no 2026/0147', '2026/0147'),
    ('Facture : INV-88', 'INV-88'),
    ('Invoice # 7741', '7741'),
    # Lu malgré le retour à la ligne : l'extraction PDF coupe souvent là
    # une mise en page sur deux lignes, et refuser ce cas perdrait un
    # numéro sur deux.
    ('FACTURE\nN° 12345', '12345'),
])
def test_numero_de_facture(texte, attendu):
    assert chercher_numero(texte) == attendu


def test_un_mot_n_est_pas_un_numero():
    """« Facture acquittée » ne doit pas devenir le numéro FA-ACQUITTEE.

    Un numéro de facture porte au moins un chiffre.
    """
    assert chercher_numero('Facture acquittée') is None
    assert chercher_numero('Facture du 12 mars') is None


# ── 4. Dates ────────────────────────────────────────────────────────────────

def test_le_jour_vient_avant_le_mois():
    """Format français. Lire « 05/11 » comme le 11 mai décalerait toutes
    les échéances de six mois, et l'erreur ne se verrait qu'au paiement."""
    assert dates_du_texte('le 05/11/2026')[0] == date(2026, 11, 5)


@pytest.mark.parametrize('texte,attendu', [
    ('12/03/2026', date(2026, 3, 12)),
    ('12-03-2026', date(2026, 3, 12)),
    ('12.03.2026', date(2026, 3, 12)),
    ('12/03/26', date(2026, 3, 12)),
    ('12 mars 2026', date(2026, 3, 12)),
    ('1er avril 2026', date(2026, 4, 1)),
    ('30 février 2026', None),               # date impossible
])
def test_formats_de_date(texte, attendu):
    trouvees = dates_du_texte(texte)
    assert (trouvees[0] if trouvees else None) == attendu


def test_une_annee_a_deux_chiffres_est_recente():
    """Une facture est un document récent : « 24 » est 2024, jamais 1924."""
    assert dates_du_texte('01/01/24')[0].year == 2024


def test_l_emission_et_l_echeance_sont_distinguees():
    """Par PROXIMITÉ de l'étiquette, pas par ordre d'apparition.

    Une facture porte souvent trois ou quatre dates — émission, échéance,
    période, date de commande — et prendre « la première » revient à tirer
    au sort.
    """
    resultat = detecter_facture(pdf_de(FACTURE_SIMPLE))
    assert resultat['champs']['date_emission'] == date(2026, 3, 12)
    assert resultat['champs']['date_echeance'] == date(2026, 4, 11)


def test_une_echeance_anterieure_a_l_emission_est_ecartee():
    """C'est une lecture fausse, pas une facture étrange.

    La garder proposerait de payer avant d'avoir reçu.
    """
    resultat = detecter_facture(pdf_de([
        'FACTURE N° X-1',
        'Date de facture : 12/03/2026',
        "Date d'échéance : 01/01/2020",
        'Total HT 100,00',
        'TVA 20 % 20,00',
        'Total TTC 120,00',
    ]))
    assert resultat['champs']['date_echeance'] is None


# ── 5. Montants et taux ─────────────────────────────────────────────────────

def test_les_trois_montants_sont_lus():
    champs = detecter_facture(pdf_de(FACTURE_SIMPLE))['champs']
    assert champs['total_ht'] == Decimal('225.50')
    assert champs['total_tva'] == Decimal('45.10')
    assert champs['total_ttc'] == Decimal('270.60')


def test_un_numero_de_tva_n_est_jamais_lu_comme_un_montant():
    """DÉFAUT MESURÉ, et sérieux.

    L'étiquette « TVA » mordait sur la ligne « TVA intracommunautaire :
    FR83404833048 » et en lisait le numéro comme un montant : la facture
    repartait avec 83 404 833 048 € de TVA. Ce n'est pas une imprécision,
    c'est une écriture comptable absurde — et rien, en aval, ne l'aurait
    rattrapée avant le rapprochement bancaire.
    """
    champs = detecter_facture(pdf_de(FACTURE_SIMPLE))['champs']
    assert champs['total_tva'] == Decimal('45.10')


def test_la_ligne_du_siret_ne_fournit_aucun_montant():
    """Même famille : un SIRET est 14 chiffres, soit un montant énorme.

    Le filtre est exact et non heuristique — il retire les lignes portant
    un identifiant déjà validé par sa clé de contrôle.
    """
    from apps.purchases.invoice_detection import texte_sans_identifiants

    texte = f'Total HT 100,00\nSIRET {SIRET_VALIDE}\nTVA 20,00'
    propre = texte_sans_identifiants(texte, siret=SIRET_VALIDE)
    assert SIRET_VALIDE not in propre.replace(' ', '')
    assert 'Total HT 100,00' in propre
    assert 'TVA 20,00' in propre


def test_les_montants_coherents_sont_signales_comme_tels():
    resultat = detecter_facture(pdf_de(FACTURE_SIMPLE))
    assert resultat['totaux']['coherent'] is True
    assert resultat['totaux']['ecart'] == Decimal('0.00')


def test_un_taux_usuel_est_prefere_a_une_remise():
    """Une facture porte d'autres pourcentages : remise, acompte, pénalité.

    Prendre le premier venu donnerait « 2 % » pour une remise.
    """
    assert taux_du_texte('Remise 2 % ... TVA 20 % ...') == Decimal('20')
    assert taux_du_texte('Remise 3 %') == Decimal('3')   # faute d'usuel


def test_le_dernier_nombre_de_la_ligne_est_le_montant():
    """Dans « Total HT 3 lignes 1 234,56 € », le premier nombre est un
    compte de lignes."""
    champs = detecter_facture(pdf_de([
        'FACTURE N° Z-9',
        'Date de facture : 02/02/2026',
        'Total HT 3 lignes 1 234,56',
        'TVA 20 % 246,91',
        'Total TTC 1 481,47',
    ]))['champs']
    assert champs['total_ht'] == Decimal('1234.56')


def test_net_a_payer_vaut_total_ttc():
    champs = detecter_facture(pdf_de([
        'FACTURE N° Y-3',
        'Date de facture : 02/02/2026',
        'Total HT 100,00',
        'TVA 20,00',
        'Net à payer 120,00',
    ]))['champs']
    assert champs['total_ttc'] == Decimal('120.00')


# ── 6. La réconciliation : le contrôle décisif ──────────────────────────────

def test_trois_montants_incoherents_sont_denonces_et_non_corriges():
    """On ne sait pas lequel est faux.

    En choisir un reviendrait à inventer un chiffre comptable. On le dit,
    et l'écran demande de vérifier les trois.
    """
    ht, tva, ttc, rapport = reconcilier(
        Decimal('100'), Decimal('20'), Decimal('130'))
    assert (ht, tva, ttc) == (Decimal('100'), Decimal('20'), Decimal('130'))
    assert rapport['coherent'] is False
    assert rapport['ecart'] == Decimal('-10.00')
    assert 'écart' in rapport['message']


@pytest.mark.parametrize('ht,tva,ttc,manquant', [
    (Decimal('100'), Decimal('20'), None, 'TTC'),
    (Decimal('100'), None, Decimal('120'), 'TVA'),
    (None, Decimal('20'), Decimal('120'), 'HT'),
])
def test_le_montant_manquant_est_deduit(ht, tva, ttc, manquant):
    """Une soustraction est sûre ; une case vide se remplit de travers."""
    ht, tva, ttc, rapport = reconcilier(ht, tva, ttc)
    assert (ht, tva, ttc) == (Decimal('100.00'), Decimal('20.00'),
                              Decimal('120.00'))
    assert rapport['coherent'] is True
    assert manquant in rapport['deduits'][0]


def test_le_ht_se_deduit_du_ttc_et_du_taux():
    ht, tva, ttc, rapport = reconcilier(None, None, Decimal('120'),
                                        taux=Decimal('20'))
    assert ht == Decimal('100.00')
    assert tva == Decimal('20.00')
    assert rapport['coherent'] is True


def test_un_centime_d_arrondi_est_tolere():
    """Les arrondis par ligne ne tombent pas toujours sur le total.

    Refuser un centime d'écart signalerait en rouge des factures justes, et
    on apprendrait à ignorer l'avertissement.
    """
    _ht, _tva, _ttc, rapport = reconcilier(
        Decimal('100.00'), Decimal('20.00'), Decimal('120.01'))
    assert rapport['coherent'] is True


def test_deux_centimes_ne_le_sont_pas():
    _ht, _tva, _ttc, rapport = reconcilier(
        Decimal('100.00'), Decimal('20.00'), Decimal('120.02'))
    assert rapport['coherent'] is False


def test_montants_incomplets_sans_taux_restent_incomplets():
    """Mieux vaut une case vide qu'un chiffre inventé."""
    ht, tva, ttc, rapport = reconcilier(Decimal('100'), None, None)
    assert (tva, ttc) == (None, None)
    assert rapport['coherent'] is None
    assert 'incomplets' in rapport['message']


# ── 7. Rattachement au fournisseur ──────────────────────────────────────────

pytestmark = pytest.mark.django_db


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


def creer_fournisseur(company, nom='MATERIAUX DU NORD SAS', siret='',
                      tva=''):
    from apps.purchases.models import Supplier
    return Supplier.objects.create(company=company, name=nom, siret=siret,
                                   vat_number=tva, is_active=True)


def test_le_fournisseur_est_reconnu_par_son_siret(entreprise):
    attendu = creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    creer_fournisseur(entreprise, nom='AUTRE SARL')
    resultat = chercher_fournisseur(entreprise, siret=SIRET_VALIDE)
    assert resultat['fournisseur'] == attendu
    assert resultat['certitude'] == 'sure'


def test_le_fournisseur_est_reconnu_par_son_numero_de_tva(entreprise):
    attendu = creer_fournisseur(entreprise, tva=TVA_VALIDE)
    resultat = chercher_fournisseur(entreprise, numero_tva=TVA_VALIDE)
    assert resultat['fournisseur'] == attendu
    assert resultat['motif'] == 'tva'


def test_le_numero_de_tva_est_compare_sans_les_espaces(entreprise):
    attendu = creer_fournisseur(entreprise, tva='FR 40 404833048')
    resultat = chercher_fournisseur(entreprise, numero_tva='FR40404833048')
    assert resultat['fournisseur'] == attendu


def test_le_nom_ne_donne_qu_une_certitude_probable(entreprise):
    attendu = creer_fournisseur(entreprise, nom='MATERIAUX DU NORD SAS')
    resultat = chercher_fournisseur(
        entreprise, texte='Facture de MATERIAUX DU NORD SAS du 12/03')
    assert resultat['fournisseur'] == attendu
    assert resultat['certitude'] == 'probable'


def test_deux_noms_possibles_ne_rattachent_rien(entreprise):
    """Rattacher au mauvais fait payer la dette d'un autre.

    En cas d'ambiguïté, on ne choisit pas : on le dit et l'utilisateur
    tranche.
    """
    creer_fournisseur(entreprise, nom='MARTIN BOIS')
    creer_fournisseur(entreprise, nom='MARTIN BOIS ET DERIVES')
    resultat = chercher_fournisseur(
        entreprise, texte='facture MARTIN BOIS ET DERIVES')
    assert resultat['fournisseur'] is None
    assert resultat['motif'] == 'nom_ambigu'
    assert len(resultat['candidats']) == 2


def test_le_fournisseur_d_une_autre_entreprise_n_est_pas_propose(
        entreprise, autre_entreprise):
    creer_fournisseur(autre_entreprise, siret=SIRET_VALIDE)
    resultat = chercher_fournisseur(entreprise, siret=SIRET_VALIDE)
    assert resultat['fournisseur'] is None


def test_un_fournisseur_inactif_n_est_pas_propose(entreprise):
    fournisseur = creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    fournisseur.is_active = False
    fournisseur.save()
    assert chercher_fournisseur(entreprise, siret=SIRET_VALIDE)['fournisseur'] is None


# ── 8. Le détecteur complet, sur un vrai PDF ────────────────────────────────

def test_detection_complete(entreprise):
    attendu = creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    resultat = detecter_facture(pdf_de(FACTURE_SIMPLE), company=entreprise)

    assert resultat['texte_trouve'] is True
    assert resultat['champs']['numero'] == 'FA-2026-0147'
    assert resultat['champs']['date_emission'] == date(2026, 3, 12)
    assert resultat['champs']['date_echeance'] == date(2026, 4, 11)
    assert resultat['champs']['total_ht'] == Decimal('225.50')
    assert resultat['champs']['total_ttc'] == Decimal('270.60')
    assert resultat['champs']['taux_tva'] == Decimal('20')
    assert resultat['champs']['siret'] == SIRET_VALIDE
    assert resultat['champs']['numero_tva'] == TVA_VALIDE
    assert resultat['fournisseur']['fournisseur'] == attendu
    assert resultat['totaux']['coherent'] is True


def test_la_detection_n_ecrit_rien(entreprise):
    """La propriété qui justifie l'écran de relecture.

    Une facture crée une dette : l'extraction ne doit jamais devenir une
    écriture sans qu'un humain l'ait vue.
    """
    from apps.purchases.models import SupplierInvoice
    creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    detecter_facture(pdf_de(FACTURE_SIMPLE), company=entreprise)
    assert SupplierInvoice.objects.count() == 0


def test_sans_entreprise_aucun_fournisseur_n_est_cherche():
    """Appel hors requête (commande, shell) : pas de cloisonnement possible,
    donc on ne propose personne plutôt que de chercher partout."""
    resultat = detecter_facture(pdf_de(FACTURE_SIMPLE))
    assert resultat['fournisseur']['fournisseur'] is None
    assert resultat['champs']['siret'] == SIRET_VALIDE


# ── 9. Les écrans : déposer, relire, confirmer ──────────────────────────────

def creer_compte(nom, company, role='admin'):
    from django.contrib.auth.models import User

    from apps.accounts.models import UserProfile

    utilisateur = User.objects.create_user(username=nom, password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = role
    profil.save()
    profil.companies.add(company)
    return User.objects.get(pk=utilisateur.pk)


@pytest.fixture
def acheteur(entreprise):
    return creer_compte('acheteur', entreprise)


def deposer(client, octets, nom='facture.pdf'):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse

    return client.post(reverse('purchases:invoice_import'), {
        'fichier': SimpleUploadedFile(nom, octets,
                                      content_type='application/pdf')})


def test_l_ecran_de_depot_s_affiche(client, acheteur):
    from django.urls import reverse

    client.force_login(acheteur)
    reponse = client.get(reverse('purchases:invoice_import'))
    assert reponse.status_code == 200
    # L'écran annonce franchement ce que la lecture ne sait pas faire.
    assert 'scanné' in reponse.content.decode()


def test_le_depot_mene_a_la_relecture_sans_rien_enregistrer(client, acheteur,
                                                             entreprise):
    """La propriété centrale de cet import.

    Une facture crée une dette et part en comptabilité : l'extraction
    propose, un humain valide. Enregistrer au dépôt transformerait une
    erreur de lecture en écriture comptable.
    """
    from apps.purchases.models import SupplierInvoice

    creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    client.force_login(acheteur)
    reponse = deposer(client, pdf_de(FACTURE_SIMPLE))

    assert reponse.status_code == 200
    assert SupplierInvoice.objects.count() == 0
    corps = reponse.content.decode()
    assert 'FA-2026-0147' in corps
    assert '225.50' in corps or '225,50' in corps


def test_la_relecture_preselectionne_le_fournisseur_reconnu(client, acheteur,
                                                             entreprise):
    fournisseur = creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    client.force_login(acheteur)
    reponse = deposer(client, pdf_de(FACTURE_SIMPLE))
    assert reponse.context['detection']['fournisseur']['fournisseur'] == fournisseur
    assert f'value="{fournisseur.pk}"' in reponse.content.decode()


def test_le_parcours_complet_enregistre_la_facture_et_le_pdf(client, acheteur,
                                                              entreprise):
    from django.urls import reverse

    from apps.purchases.models import SupplierInvoice

    fournisseur = creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    client.force_login(acheteur)
    deposer(client, pdf_de(FACTURE_SIMPLE))

    client.post(reverse('purchases:invoice_import_confirm'), {
        'supplier': fournisseur.pk,
        'numero': 'FA-2026-0147',
        'date_emission': '2026-03-12',
        'date_echeance': '2026-04-11',
        'total_ht': '225.50',
        'total_tva': '45.10',
        'total_ttc': '270.60',
        'notes': '',
    })

    facture = SupplierInvoice.objects.get()
    assert facture.supplier == fournisseur
    assert facture.number == 'FA-2026-0147'
    assert facture.issue_date == date(2026, 3, 12)
    assert facture.total_ttc == Decimal('270.60')
    # Le PDF est la pièce justificative : le perdre viderait l'import de
    # son intérêt.
    assert facture.fichier
    with facture.fichier.open('rb') as flux:
        assert flux.read(4) == b'%PDF'


def test_la_confirmation_prend_les_valeurs_corrigees(client, acheteur,
                                                      entreprise):
    """L'écran de relecture n'a de sens que si la correction gagne.

    Repartir de la détection ferait silencieusement perdre ce que
    l'utilisateur a rectifié — le pire des deux mondes : on lui demande de
    vérifier, et on ignore sa réponse.
    """
    from django.urls import reverse

    from apps.purchases.models import SupplierInvoice

    fournisseur = creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    client.force_login(acheteur)
    deposer(client, pdf_de(FACTURE_SIMPLE))

    client.post(reverse('purchases:invoice_import_confirm'), {
        'supplier': fournisseur.pk,
        'numero': 'CORRIGE-1',
        'date_emission': '2026-03-13',
        'total_ht': '999.99',
        'total_tva': '200.00',
        'total_ttc': '1199.99',
    })

    facture = SupplierInvoice.objects.get()
    assert facture.number == 'CORRIGE-1'
    assert facture.issue_date == date(2026, 3, 13)
    assert facture.total_ht == Decimal('999.99')


def test_sans_fournisseur_rien_n_est_enregistre(client, acheteur, entreprise):
    """Une facture sans fournisseur ne peut être ni rapprochée ni payée."""
    from django.urls import reverse

    from apps.purchases.models import SupplierInvoice

    client.force_login(acheteur)
    deposer(client, pdf_de(FACTURE_SIMPLE))
    client.post(reverse('purchases:invoice_import_confirm'), {
        'supplier': '', 'date_emission': '2026-03-12'})
    assert SupplierInvoice.objects.count() == 0


def test_un_fournisseur_d_une_autre_entreprise_est_refuse(
        client, acheteur, entreprise, autre_entreprise):
    """La liste déroulante était déjà bornée ; un identifiant forgé dans le
    POST rattacherait la facture au fournisseur d'une autre société."""
    from django.urls import reverse

    from apps.purchases.models import SupplierInvoice

    etranger = creer_fournisseur(autre_entreprise, nom='EXTERNE SARL')
    client.force_login(acheteur)
    deposer(client, pdf_de(FACTURE_SIMPLE))
    client.post(reverse('purchases:invoice_import_confirm'), {
        'supplier': etranger.pk, 'date_emission': '2026-03-12',
        'total_ttc': '270.60'})
    assert SupplierInvoice.objects.count() == 0


def test_sans_date_de_facture_rien_n_est_enregistre(client, acheteur,
                                                     entreprise):
    """Elle détermine l'exercice comptable et l'échéance."""
    from django.urls import reverse

    from apps.purchases.models import SupplierInvoice

    fournisseur = creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    client.force_login(acheteur)
    deposer(client, pdf_de(FACTURE_SIMPLE))
    client.post(reverse('purchases:invoice_import_confirm'), {
        'supplier': fournisseur.pk, 'date_emission': ''})
    assert SupplierInvoice.objects.count() == 0


def test_un_fichier_qui_n_est_pas_un_pdf_est_refuse_a_l_ecran(client,
                                                               acheteur):
    client.force_login(acheteur)
    reponse = deposer(client, b'du texte, pas un PDF', nom='faux.pdf')
    assert reponse.status_code in (301, 302)   # redirigé avec un message


def test_la_relecture_d_une_facture_existante_ne_modifie_rien(
        client, acheteur, entreprise):
    """Elle compare, elle n'écrit pas.

    Sert à vérifier un montant contesté sans ouvrir le PDF à la main.
    """
    from django.core.files.base import ContentFile
    from django.urls import reverse

    from apps.purchases.models import SupplierInvoice

    fournisseur = creer_fournisseur(entreprise, siret=SIRET_VALIDE)
    facture = SupplierInvoice.objects.create(
        company=entreprise, supplier=fournisseur, number='AUTRE-999',
        issue_date=date(2026, 1, 1), total_ht=Decimal('1'),
        total_tva=Decimal('0'), total_ttc=Decimal('1'))
    facture.fichier.save('f.pdf', ContentFile(pdf_de(FACTURE_SIMPLE)))

    client.force_login(acheteur)
    reponse = client.get(reverse('purchases:invoice_redetect',
                                 args=[facture.pk]))
    assert reponse.status_code == 200

    facture.refresh_from_db()
    assert facture.number == 'AUTRE-999'
    assert facture.total_ht == Decimal('1')
    # L'écart entre le PDF et l'enregistrement est bien visible.
    assert 'FA-2026-0147' in reponse.content.decode()


def test_la_relecture_d_une_facture_sans_pdf_le_dit(client, acheteur,
                                                     entreprise):
    from django.urls import reverse

    from apps.purchases.models import SupplierInvoice

    fournisseur = creer_fournisseur(entreprise, nom='SANS PDF SARL')
    facture = SupplierInvoice.objects.create(
        company=entreprise, supplier=fournisseur,
        issue_date=date(2026, 1, 1))
    client.force_login(acheteur)
    reponse = client.get(reverse('purchases:invoice_redetect',
                                 args=[facture.pk]), follow=True)
    assert reponse.status_code == 200
    assert 'rien à relire' in reponse.content.decode()


def test_la_relecture_d_une_facture_d_une_autre_entreprise_est_introuvable(
        client, acheteur, autre_entreprise):
    from django.urls import reverse

    from apps.purchases.models import SupplierInvoice

    etranger = creer_fournisseur(autre_entreprise, nom='EXTERNE SARL')
    facture = SupplierInvoice.objects.create(
        company=autre_entreprise, supplier=etranger,
        issue_date=date(2026, 1, 1))
    client.force_login(acheteur)
    assert client.get(reverse('purchases:invoice_redetect',
                              args=[facture.pk])).status_code == 404


def test_un_anonyme_ne_peut_rien_importer(client):
    from django.urls import reverse

    reponse = client.get(reverse('purchases:invoice_import'))
    assert reponse.status_code in (301, 302)
