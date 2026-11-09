# -*- coding: utf-8 -*-
"""Le client doit VOIR ses photos sans avoir à les télécharger.

Jusqu'ici, le portail affichait une icône et un bouton « Télécharger » :
pour savoir ce que montrait une photo, le client devait la faire descendre
en entier. Sur un chantier de vingt photos prises au téléphone, cela fait
quatre-vingts mégaoctets.

DEUX DÉCISIONS QUE CES TESTS TIENNENT.

1. **De vraies miniatures, pas l'original rétréci par le navigateur.**
   `style="width:64px"` sur la photo d'origine donne la même image à
   l'écran et ne change rien au coût — le fichier entier descend quand
   même. Une miniature de 480 pixels pèse une trentaine de kilooctets.

2. **Le même contrôle que la liste, mot pour mot.** Même entreprise, même
   courriel de client, `visible_to_client`. Un aperçu plus permissif que la
   page qui le porte serait une fuite d'autant plus discrète qu'aucun écran
   ne la montrerait.

Et une règle apprise la veille sur la galerie du chantier : **on ne pose
jamais une balise `<img>` sans savoir d'avance qu'elle aboutira.** Le
gabarit ne le fait que pour les extensions que Pillow lit sans greffon ;
un PDF ou un HEIC garde son icône, au lieu d'afficher une vignette cassée.
"""

import io as _io
import os
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def media_temporaire(settings, tmp_path):
    """Les téléversements ET les miniatures dans un dossier jetable."""
    settings.MEDIA_ROOT = str(tmp_path)
    return tmp_path


def _octets_jpeg(largeur=1200, hauteur=800, exif=None):
    from PIL import Image

    tampon = _io.BytesIO()
    image = Image.new('RGB', (largeur, hauteur), (200, 30, 30))
    if exif is None:
        image.save(tampon, 'JPEG')
    else:
        image.save(tampon, 'JPEG', exif=exif)
    return tampon.getvalue()


def _octets_png_transparent(largeur=300, hauteur=300):
    from PIL import Image

    tampon = _io.BytesIO()
    image = Image.new('RGBA', (largeur, hauteur), (0, 0, 0, 0))
    image.save(tampon, 'PNG')
    return tampon.getvalue()


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Volt SARL', slug='volt-sarl')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Ampere SA', slug='ampere-sa')


@pytest.fixture
def chantier_du_client(entreprise, django_user_model, client):
    """Un client connecté à son portail, avec un chantier à lui."""
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer
    from apps.portals.models import ClientPortalAccount

    courriel = 'martin@exemple.fr'
    utilisateur = django_user_model.objects.create_user(
        username=courriel, email=courriel, password='motdepasse-test')
    ClientPortalAccount.objects.create(
        company=entreprise, user=utilisateur, email=courriel,
        first_name='Paul', last_name='Martin')
    acheteur = Customer.objects.create(
        company=entreprise, name='Paul Martin', email=courriel)
    projet = BTPProject.objects.create(
        company=entreprise, name='Rénovation Martin', customer=acheteur,
        start_date=date(2026, 3, 2))
    client.force_login(utilisateur)
    return client, projet


def _document(projet, nom_fichier, octets, visible=True, telechargeable=True):
    from apps.btp.models import ProjectDocument
    return ProjectDocument.objects.create(
        project=projet, name=nom_fichier, doc_type='photo',
        file=SimpleUploadedFile(nom_fichier, octets),
        visible_to_client=visible, client_can_download=telechargeable)


def _url_miniature(projet, document):
    return reverse('client_portal:project_document_thumbnail',
                   args=[projet.pk, document.pk])


# ── Le fabricant de miniatures ──────────────────────────────────────────────

def test_seules_les_extensions_sues_sont_miniaturables():
    """On ne promet un aperçu que là où Pillow sait le produire.

    Le HEIC des iPhone en est exclu : Pillow ne l'ouvre pas sans greffon,
    et tenter puis échouer afficherait une vignette cassée.
    """
    from apps.core import miniatures

    assert miniatures.peut_etre_miniaturee('photo.JPG')
    assert miniatures.peut_etre_miniaturee('dossier/vue.webp')
    assert not miniatures.peut_etre_miniaturee('plan.pdf')
    assert not miniatures.peut_etre_miniaturee('iphone.heic')
    assert not miniatures.peut_etre_miniaturee('logo.svg')
    assert not miniatures.peut_etre_miniaturee('')
    assert not miniatures.peut_etre_miniaturee(None)


def test_la_miniature_est_bien_plus_legere_que_l_original(chantier_du_client):
    """La raison d'être de tout ce code."""
    from PIL import Image

    from apps.core import miniatures

    _client, projet = chantier_du_client
    octets = _octets_jpeg(2400, 1600)
    document = _document(projet, 'facade.jpg', octets)

    chemin = miniatures.miniature(document.file)

    assert chemin is not None
    with Image.open(chemin) as vignette:
        assert max(vignette.size) <= miniatures.LARGEUR_PAR_DEFAUT
    assert os.path.getsize(chemin) < len(octets) / 2, (
        'une miniature qui pese autant que l-original ne sert a rien')


def test_une_photo_de_telephone_n_est_pas_couchee(chantier_du_client):
    """L'orientation EXIF, et ce n'est pas un détail sur un chantier.

    Une photo prise en portrait est stockée en paysage avec une étiquette
    de rotation. Sans `exif_transpose`, la moitié des vignettes seraient
    couchées — et personne ne comprendrait pourquoi.
    """
    from PIL import Image

    from apps.core import miniatures

    _client, projet = chantier_du_client
    exif = Image.Exif()
    exif[274] = 6                       # rotation de 90 degres
    document = _document(projet, 'portrait.jpg',
                         _octets_jpeg(1200, 800, exif=exif.tobytes()))

    chemin = miniatures.miniature(document.file)

    with Image.open(chemin) as vignette:
        assert vignette.height > vignette.width, (
            'la rotation EXIF n-a pas ete appliquee : vignette couchee')


def test_une_image_transparente_est_posee_sur_du_blanc(chantier_du_client):
    """Un PNG transparent converti en RGB donne un fond NOIR.

    Un plan ou un logo sur fond clair en devient méconnaissable.
    """
    from PIL import Image

    from apps.core import miniatures

    _client, projet = chantier_du_client
    document = _document(projet, 'plan.png', _octets_png_transparent())

    chemin = miniatures.miniature(document.file)

    with Image.open(chemin) as vignette:
        assert vignette.getpixel((5, 5)) == (255, 255, 255), (
            'fond noir : l-aplatissement sur blanc n-a pas eu lieu')


def test_la_miniature_n_est_fabriquee_qu_une_fois(chantier_du_client):
    """Sinon chaque affichage de la page relance Pillow sur chaque photo."""
    from apps.core import miniatures

    _client, projet = chantier_du_client
    document = _document(projet, 'facade.jpg', _octets_jpeg())

    premier = miniatures.miniature(document.file)
    empreinte = os.stat(premier).st_mtime_ns
    second = miniatures.miniature(document.file)

    assert second == premier
    assert os.stat(second).st_mtime_ns == empreinte, (
        'la miniature a ete refabriquee alors qu-elle existait deja')


def test_un_fichier_illisible_ne_fait_pas_tomber_la_page(chantier_du_client):
    """Une miniature est un confort ; son échec ne doit rien interrompre."""
    from apps.core import miniatures

    _client, projet = chantier_du_client
    document = _document(projet, 'tronquee.jpg', b'ceci-n-est-pas-une-image')

    assert miniatures.miniature(document.file) is None


def test_les_miniatures_ne_sont_jamais_servies_par_media():
    """Une miniature d'un document confidentiel reste confidentielle.

    Le dossier n'est dans aucune des listes d'autorisation de
    media_access : /media/miniatures/... rend donc 404, et seule une vue
    qui a vérifié les droits peut en servir une.
    """
    from apps.core import media_access, miniatures

    prefixe = miniatures.DOSSIER + '/'
    assert prefixe not in media_access.PREFIXES_PUBLICS
    assert prefixe not in media_access.PREFIXES_AUTHENTIFIES


# ── La vue du portail : mêmes droits que la liste ───────────────────────────

def test_le_client_voit_la_miniature_de_sa_photo(chantier_du_client):
    client, projet = chantier_du_client
    document = _document(projet, 'facade.jpg', _octets_jpeg())

    reponse = client.get(_url_miniature(projet, document))

    assert reponse.status_code == 200
    assert reponse['Content-Type'] == 'image/jpeg'
    assert len(b''.join(reponse.streaming_content)) > 0


def test_un_document_cache_au_client_n_a_pas_de_miniature(chantier_du_client):
    """`visible_to_client=False` : il n'est pas dans la liste non plus."""
    client, projet = chantier_du_client
    document = _document(projet, 'interne.jpg', _octets_jpeg(), visible=False)

    assert client.get(_url_miniature(projet, document)).status_code == 404


def test_un_pdf_n_a_pas_de_miniature(chantier_du_client):
    client, projet = chantier_du_client
    document = _document(projet, 'devis.pdf', b'%PDF-1.4 faux')

    assert client.get(_url_miniature(projet, document)).status_code == 404


def test_le_chantier_d_un_autre_client_est_refuse(chantier_du_client,
                                                  autre_entreprise):
    """Le contrôle qui justifie que cette vue existe."""
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer

    client, _projet = chantier_du_client
    voisin = Customer.objects.create(
        company=autre_entreprise, name='Autre', email='autre@exemple.fr')
    chantier_voisin = BTPProject.objects.create(
        company=autre_entreprise, name='Chantier Ampere', customer=voisin,
        start_date=date(2026, 4, 1))
    document = _document(chantier_voisin, 'secret.jpg', _octets_jpeg())

    assert client.get(
        _url_miniature(chantier_voisin, document)).status_code == 404


def test_un_visiteur_anonyme_est_renvoye_a_la_connexion(client,
                                                        chantier_du_client):
    _connecte, projet = chantier_du_client
    document = _document(projet, 'facade.jpg', _octets_jpeg())

    anonyme = client.__class__()
    reponse = anonyme.get(_url_miniature(projet, document))

    assert reponse.status_code in (302, 403)


# ── Ce que la page montre ───────────────────────────────────────────────────

def _page_documents(client, projet):
    reponse = client.get(reverse('client_portal:project_documents',
                                 args=[projet.pk]))
    assert reponse.status_code == 200
    return reponse.content.decode()


def test_la_page_affiche_la_vignette_d_une_photo(chantier_du_client):
    client, projet = chantier_du_client
    document = _document(projet, 'facade.jpg', _octets_jpeg())

    contenu = _page_documents(client, projet)

    assert _url_miniature(projet, document) in contenu
    assert '<img src="%s"' % _url_miniature(projet, document) in contenu


def test_la_page_garde_une_icone_pour_un_pdf(chantier_du_client):
    """On ne pose jamais une balise <img> qui n'aboutira pas.

    C'est la leçon de la galerie du chantier, livrée la veille avec
    toutes ses vignettes cassées.
    """
    client, projet = chantier_du_client
    document = _document(projet, 'devis.pdf', b'%PDF-1.4 faux')

    contenu = _page_documents(client, projet)

    assert _url_miniature(projet, document) not in contenu
    assert 'bi-file-earmark-pdf' in contenu


def test_une_photo_non_telechargeable_reste_visible(chantier_du_client):
    """`visible_to_client` autorise à VOIR, `client_can_download` à EMPORTER.

    Un aperçu relève du premier. Le document est déjà listé au client avec
    son nom, son type et sa date ; sa vignette ne le rend pas plus public.
    Mais aucun lien de téléchargement ne doit l'accompagner.
    """
    client, projet = chantier_du_client
    document = _document(projet, 'plan.jpg', _octets_jpeg(),
                         telechargeable=False)

    contenu = _page_documents(client, projet)

    assert _url_miniature(projet, document) in contenu
    assert reverse('client_portal:project_document_download',
                   args=[projet.pk, document.pk]) not in contenu
