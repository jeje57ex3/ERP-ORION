"""Placement visuel des cadres sur un modèle de devis.

On pose un cadre là où la valeur doit s'écrire, et la machine convertit. La
conversion est le cœur du sujet, et la seule chose qui puisse réellement mal
tourner : **l'écran compte en pixels depuis le HAUT, le PDF compte en points
depuis le BAS**. Les deux axes verticaux sont inversés — se tromper de sens
imprime en bas ce qu'on a posé en haut, et l'erreur ne se voit qu'à la
première génération.

Ces tests éprouvent donc la boucle entière : des coordonnées venues de
l'éditeur, enregistrées, puis relues dans le PDF produit. Pas la souris — le
navigateur n'est pas ici — mais tout ce qui vient après elle.
"""

import io
import json
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile

pytestmark = pytest.mark.django_db


def _pdf_vierge(pages=1, largeur=595, hauteur=842):
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=(largeur, hauteur))
    for numero in range(pages):
        feuille.setFont('Helvetica-Bold', 16)
        feuille.drawString(40, hauteur - 50, 'ENTREPRISE DUPONT')
        feuille.showPage()
    feuille.save()
    tampon.seek(0)
    return tampon.getvalue()


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


@pytest.fixture
def modele(entreprise):
    from apps.sales.models import QuoteTemplate
    objet = QuoteTemplate.objects.create(
        company=entreprise, name='Devis standard', is_default=True)
    objet.pdf.save('modele.pdf', ContentFile(_pdf_vierge()), save=True)
    return objet


@pytest.fixture
def modele_deux_pages(entreprise):
    from apps.sales.models import QuoteTemplate
    objet = QuoteTemplate.objects.create(company=entreprise, name='Deux pages')
    objet.pdf.save('deux.pdf', ContentFile(_pdf_vierge(pages=2)), save=True)
    return objet


@pytest.fixture
def devis(entreprise):
    from apps.crm.models import Customer
    from apps.sales.models import Quote

    client = Customer.objects.create(
        company=entreprise, code='CLI-0042', name='Entreprise Exemple SARL')
    return Quote.objects.create(
        company=entreprise, customer=client, number='DEV-2026-0042',
        total_ht=Decimal('12400.00'), total_tva=Decimal('2480.00'),
        total_ttc=Decimal('14880.00'),
    )


@pytest.fixture
def connecte(client, django_user_model, entreprise, monkeypatch):
    utilisateur = django_user_model.objects.create_user(
        username='commercial', password='motdepasse-test')
    client.force_login(utilisateur)
    from apps.sales import views_quote_templates as modeles
    monkeypatch.setattr(modeles, '_entreprise', lambda requete: entreprise)
    return client


def _enregistrer(client, modele, cadres):
    return client.post(
        f'/sales/devis/modeles/{modele.pk}/cadres/enregistrer/',
        data=json.dumps({'cadres': cadres}),
        content_type='application/json',
    )


# ── Le rendu de la page, fond de l'éditeur ──────────────────────────────────

def test_la_page_est_servie_en_png(connecte, modele):
    reponse = connecte.get(f'/sales/devis/modeles/{modele.pk}/page/1.png')
    assert reponse.status_code == 200
    assert reponse['Content-Type'] == 'image/png'
    assert reponse.content[:8] == b'\x89PNG\r\n\x1a\n'


def test_une_page_inexistante_est_refusee(connecte, modele):
    assert connecte.get(
        f'/sales/devis/modeles/{modele.pk}/page/7.png').status_code == 404


def test_l_echelle_du_rendu_est_exacte(modele):
    """L'éditeur convertit pixels → points en divisant par cette échelle.

    Si le rendu ne la respectait pas, chaque cadre serait décalé
    proportionnellement — d'autant plus loin qu'il est bas dans la page.
    """
    from apps.sales.quote_pdf import ECHELLE_EDITEUR, rendre_page_en_png
    from PIL import Image

    tampon, largeur_pt, hauteur_pt = rendre_page_en_png(modele)
    image = Image.open(tampon)

    assert image.width == pytest.approx(largeur_pt * ECHELLE_EDITEUR, abs=2)
    assert image.height == pytest.approx(hauteur_pt * ECHELLE_EDITEUR, abs=2)


def test_les_dimensions_des_pages_sont_connues(modele_deux_pages):
    """L'éditeur en a besoin pour inverser l'axe vertical."""
    from apps.sales.quote_pdf import dimensions_des_pages

    pages = dimensions_des_pages(modele_deux_pages)
    assert len(pages) == 2
    assert pages[0]['numero'] == 1
    assert pages[0]['hauteur'] == pytest.approx(842, abs=2)


# ── L'enregistrement des cadres ─────────────────────────────────────────────

def test_les_cadres_poses_sont_enregistres(connecte, modele):
    from apps.sales.models import QuoteTemplateField

    reponse = _enregistrer(connecte, modele, [
        {'cle': 'numero_devis', 'page': 1, 'x': 100, 'y': 700,
         'largeur': 160, 'hauteur': 16, 'taille': 11, 'gras': True,
         'alignement': 'left', 'prefixe': 'N° ', 'suffixe': ''},
        {'cle': 'total_ttc', 'page': 1, 'x': 380, 'y': 200,
         'largeur': 150, 'hauteur': 18, 'taille': 12, 'gras': False,
         'alignement': 'right', 'prefixe': '', 'suffixe': ' €'},
    ])

    assert reponse.status_code == 200
    assert reponse.json()['enregistres'] == 2

    champs = {c.cle: c for c in QuoteTemplateField.objects.all()}
    assert float(champs['numero_devis'].x) == 100
    assert float(champs['numero_devis'].y) == 700
    assert champs['numero_devis'].gras is True
    assert champs['numero_devis'].prefixe == 'N° '
    assert champs['total_ttc'].alignement == 'right'
    assert champs['total_ttc'].suffixe == ' €'


def test_l_enregistrement_remplace_les_anciens_cadres(connecte, modele):
    """L'éditeur envoie la liste complète.

    Un enregistrement différentiel demanderait de suivre les identifiants côté
    navigateur et de distinguer création, modification et suppression — trois
    chemins pour un écran où l'on pose et déplace librement.
    """
    from apps.sales.models import QuoteTemplateField

    _enregistrer(connecte, modele, [
        {'cle': 'numero_devis', 'page': 1, 'x': 10, 'y': 10,
         'largeur': 100, 'hauteur': 14},
        {'cle': 'date', 'page': 1, 'x': 20, 'y': 20,
         'largeur': 100, 'hauteur': 14},
    ])
    _enregistrer(connecte, modele, [
        {'cle': 'nom_client', 'page': 1, 'x': 30, 'y': 30,
         'largeur': 100, 'hauteur': 14},
    ])

    assert QuoteTemplateField.objects.count() == 1
    assert QuoteTemplateField.objects.first().cle == 'nom_client'


def test_une_valeur_inconnue_est_refusee(connecte, modele):
    """Elle viendrait d'une requête forgée, ou d'un écran plus récent :
    l'accepter enregistrerait un cadre qui n'écrira jamais rien."""
    from apps.sales.models import QuoteTemplateField

    reponse = _enregistrer(connecte, modele, [
        {'cle': 'numero_de_securite_sociale', 'page': 1, 'x': 10, 'y': 10,
         'largeur': 100, 'hauteur': 14},
    ])
    assert reponse.status_code == 400
    assert 'inconnue' in reponse.json()['erreur'].lower()
    assert QuoteTemplateField.objects.count() == 0


def test_une_page_inexistante_est_refusee_a_l_enregistrement(connecte, modele):
    reponse = _enregistrer(connecte, modele, [
        {'cle': 'date', 'page': 5, 'x': 10, 'y': 10,
         'largeur': 100, 'hauteur': 14},
    ])
    assert reponse.status_code == 400
    assert '5' in reponse.json()['erreur']


def test_un_cadre_de_taille_nulle_est_refuse(connecte, modele):
    """Il n'écrirait rien, et la réduction automatique du texte diviserait
    par zéro en cherchant une taille qui tient."""
    reponse = _enregistrer(connecte, modele, [
        {'cle': 'date', 'page': 1, 'x': 10, 'y': 10,
         'largeur': 0, 'hauteur': 14},
    ])
    assert reponse.status_code == 400


def test_un_corps_illisible_est_refuse(connecte, modele):
    reponse = connecte.post(
        f'/sales/devis/modeles/{modele.pk}/cadres/enregistrer/',
        data='ceci n est pas du json', content_type='application/json')
    assert reponse.status_code == 400


def test_l_enregistrement_est_tout_ou_rien(connecte, modele):
    """Un cadre invalide au milieu de la liste ne doit pas laisser le modèle
    sans ses anciens cadres et sans les nouveaux."""
    from apps.sales.models import QuoteTemplateField

    _enregistrer(connecte, modele, [
        {'cle': 'date', 'page': 1, 'x': 10, 'y': 10,
         'largeur': 100, 'hauteur': 14},
    ])
    reponse = _enregistrer(connecte, modele, [
        {'cle': 'nom_client', 'page': 1, 'x': 20, 'y': 20,
         'largeur': 100, 'hauteur': 14},
        {'cle': 'cle_inventee', 'page': 1, 'x': 30, 'y': 30,
         'largeur': 100, 'hauteur': 14},
    ])

    assert reponse.status_code == 400
    # L'ancien cadre est toujours la : rien n'a ete supprime.
    assert QuoteTemplateField.objects.count() == 1
    assert QuoteTemplateField.objects.first().cle == 'date'


def test_l_enregistrement_exige_un_post(connecte, modele):
    assert connecte.get(
        f'/sales/devis/modeles/{modele.pk}/cadres/enregistrer/'
    ).status_code == 405


def test_le_modele_d_une_autre_entreprise_est_hors_de_portee(
        connecte, autre_entreprise):
    from apps.sales.models import QuoteTemplate, QuoteTemplateField

    chez_eux = QuoteTemplate.objects.create(
        company=autre_entreprise, name='Leur modèle')
    chez_eux.pdf.save('x.pdf', ContentFile(_pdf_vierge()), save=True)

    for adresse in (
        f'/sales/devis/modeles/{chez_eux.pk}/cadres/',
        f'/sales/devis/modeles/{chez_eux.pk}/page/1.png',
    ):
        assert connecte.get(adresse).status_code == 404, adresse

    assert _enregistrer(connecte, chez_eux, [
        {'cle': 'date', 'page': 1, 'x': 10, 'y': 10,
         'largeur': 100, 'hauteur': 14},
    ]).status_code == 404
    assert QuoteTemplateField.objects.count() == 0


# ── L'éditeur ───────────────────────────────────────────────────────────────

def test_l_editeur_fournit_tout_ce_dont_le_navigateur_a_besoin(connecte,
                                                               modele):
    """Sans les dimensions de page ni l'échelle, le navigateur ne peut pas
    inverser l'axe vertical — et poserait les cadres à l'envers."""
    corps = connecte.get(
        f'/sales/devis/modeles/{modele.pk}/cadres/').content.decode()

    assert 'data-echelle' in corps
    assert 'data-pages' in corps
    assert 'data-cadres' in corps
    assert 'data-url-enregistrer' in corps
    assert '__PAGE__' in corps      # gabarit d'adresse des images
    assert 'csrfmiddlewaretoken' in corps or 'data-csrf' in corps


def test_l_editeur_relit_les_cadres_existants(connecte, modele):
    _enregistrer(connecte, modele, [
        {'cle': 'nom_client', 'page': 1, 'x': 42, 'y': 640,
         'largeur': 200, 'hauteur': 18},
    ])
    corps = connecte.get(
        f'/sales/devis/modeles/{modele.pk}/cadres/').content.decode()
    assert 'nom_client' in corps
    assert '42' in corps


def test_un_pdf_illisible_ne_casse_pas_l_editeur(connecte, entreprise):
    """L'écran doit le dire, et non rendre une erreur 500."""
    from apps.sales.models import QuoteTemplate

    casse = QuoteTemplate.objects.create(company=entreprise, name='Cassé')
    casse.pdf.save('casse.pdf', ContentFile(b'ceci n est pas un pdf'),
                   save=True)

    reponse = connecte.get(f'/sales/devis/modeles/{casse.pk}/cadres/')
    assert reponse.status_code == 200
    assert 'Impossible de lire' in reponse.content.decode()


# ── La boucle entière : posé à l'écran, écrit au bon endroit ───────────────

def test_un_cadre_pose_en_haut_est_imprime_en_haut(connecte, modele, devis):
    """LE test qui compte.

    L'écran compte en pixels depuis le haut, le PDF en points depuis le bas.
    Se tromper de sens imprimerait en bas ce qu'on a posé en haut — et
    l'erreur ne se verrait qu'à la première génération d'un vrai devis.
    """
    from apps.sales.quote_pdf import remplir_modele
    from pypdf import PdfReader

    # Un cadre haut dans la page : y proche de la hauteur (842).
    _enregistrer(connecte, modele, [
        {'cle': 'numero_devis', 'page': 1, 'x': 60, 'y': 760,
         'largeur': 200, 'hauteur': 18, 'taille': 11},
    ])

    octets = remplir_modele(devis, modele.__class__.objects.get(
        pk=modele.pk)).getvalue()

    # pypdf donne la position du texte : on verifie qu'il est dans le tiers
    # SUPERIEUR de la page, et non en bas.
    positions = []

    def releve(texte, matrice_police, matrice_texte, taille_police, *reste):
        if texte.strip():
            positions.append(matrice_texte[5])

    PdfReader(io.BytesIO(octets)).pages[0].extract_text(
        visitor_text=releve)

    assert positions, 'aucun texte relevé'
    assert max(positions) > 842 * 0.66, (
        'le texte posé en haut est imprimé en bas : axe vertical inversé'
    )


def test_la_valeur_est_ecrite_dans_le_cadre(connecte, modele, devis):
    from apps.sales.quote_pdf import remplir_modele
    from pypdf import PdfReader

    _enregistrer(connecte, modele, [
        {'cle': 'numero_devis', 'page': 1, 'x': 60, 'y': 700,
         'largeur': 200, 'hauteur': 18, 'taille': 11},
        {'cle': 'nom_client', 'page': 1, 'x': 60, 'y': 660,
         'largeur': 260, 'hauteur': 18},
    ])
    octets = remplir_modele(devis, modele).getvalue()
    texte = PdfReader(io.BytesIO(octets)).pages[0].extract_text()

    assert 'DEV-2026-0042' in texte
    assert 'Entreprise Exemple SARL' in texte
    assert 'ENTREPRISE DUPONT' in texte   # le modele d'origine survit


# ── La réduction automatique ────────────────────────────────────────────────

def test_un_texte_trop_long_est_reduit_pour_tenir(modele):
    """Un nom de client long dépassait du cadre et chevauchait la colonne
    voisine. Réduire est préférable à déborder."""
    from reportlab.pdfgen import canvas
    from apps.sales.models import QuoteTemplateField
    from apps.sales.quote_pdf import _taille_qui_tient

    feuille = canvas.Canvas(io.BytesIO())
    champ = QuoteTemplateField(
        cle='nom_client', page=1, x=0, y=0,
        largeur=Decimal('80'), hauteur=Decimal('16'), taille=14)

    # Un texte qui TIENT une fois reduit. Mesure : « Societe Nouvelle des
    # Travaux Publics » fait 321 pt a 14 pt et 115 pt a 5 pt -- il ne rentre
    # donc jamais dans 80 pt, et exiger qu'il tienne serait contradictoire
    # avec le plancher de lisibilite (voir le test suivant).
    nom = 'Entreprise Exemple'
    reduite = _taille_qui_tient(feuille, champ, nom)

    assert reduite < 14, 'la taille devrait avoir ete reduite'
    assert feuille.stringWidth(nom, 'Helvetica', reduite) <= 80


def test_la_reduction_s_arrete_avant_l_illisible(modele):
    """En dessous de 5 points, mieux vaut un débordement visible qu'une ligne
    qu'on ne peut pas lire : l'exploitant doit pouvoir constater que son cadre
    est trop petit."""
    from reportlab.pdfgen import canvas
    from apps.sales.models import QuoteTemplateField
    from apps.sales.quote_pdf import _taille_qui_tient

    feuille = canvas.Canvas(io.BytesIO())
    champ = QuoteTemplateField(
        cle='nom_client', page=1, x=0, y=0,
        largeur=Decimal('5'), hauteur=Decimal('16'), taille=12)

    assert _taille_qui_tient(feuille, champ, 'Un nom vraiment très long') == 5


def test_un_texte_court_garde_sa_taille(modele):
    from reportlab.pdfgen import canvas
    from apps.sales.models import QuoteTemplateField
    from apps.sales.quote_pdf import _taille_qui_tient

    feuille = canvas.Canvas(io.BytesIO())
    champ = QuoteTemplateField(
        cle='date', page=1, x=0, y=0,
        largeur=Decimal('200'), hauteur=Decimal('16'), taille=10)
    assert _taille_qui_tient(feuille, champ, '15/10/2026') == 10


# ── Le code du navigateur ───────────────────────────────────────────────────

def _fichier_js():
    import os
    from django.conf import settings

    chemin = os.path.join(
        settings.BASE_DIR, 'static', 'js', 'orion-cadres-devis.js')
    with io.open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


def test_le_navigateur_inverse_bien_l_axe_vertical():
    """La formule est la seule chose qui ne peut pas être devinée de nouveau
    sans se tromper : on garde sa présence."""
    code = _fichier_js()
    assert 'page.hauteur - (hautPx + hauteurPx) / ECHELLE' in code


def test_le_navigateur_borne_les_cadres_a_la_page():
    """Un cadre glissé hors de la page ne s'imprimerait pas, et rien ne le
    dirait — la valeur manquerait simplement sur le devis."""
    code = _fichier_js()
    assert 'Math.max(0, Math.min(' in code


def test_le_navigateur_previent_avant_de_perdre_le_placement():
    """Poser quinze cadres est long ; quitter la page sans enregistrer les
    perdrait sans un mot."""
    code = _fichier_js()
    assert 'beforeunload' in code
