# -*- coding: utf-8 -*-
"""L'onglet « Photos » d'un chantier, et ce qui doit y figurer.

Les photos d'un chantier existaient déjà, mais dispersées en trois modèles :
les documents du chantier, les photos de réserves, et les réponses aux
points de contrôle qui demandent une photo. Aucun écran ne les montrait
ensemble, et il fallait donc savoir d'avance où chercher.

Cet onglet les rassemble À LA LECTURE, sans quatrième modèle ni migration.
Les tests ci-dessous tiennent les deux décisions qui en découlent :

1. **C'est l'extension du fichier qui décide**, pas son étiquette. Un
   document de type « Photo » peut porter un PDF — il s'afficherait comme
   une image cassée. Et une vraie photo est souvent déposée sous un autre
   type. Les deux cas sont testés, dans les deux sens.

2. **Chaque vignette dit d'où elle vient.** « Fissure au plafond » ne veut
   pas dire la même chose selon qu'elle vient d'une réserve ou de l'état
   des lieux d'avant travaux.

Et le test qui compte le plus : aucune photo d'une AUTRE entreprise ne doit
jamais apparaître. Ce module a déjà connu une fuite de ce genre.
"""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Volt SARL', slug='volt-sarl')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Ampere SA', slug='ampere-sa')


@pytest.fixture
def client_crm(entreprise):
    from apps.crm.models import Customer
    return Customer.objects.create(company=entreprise, name='Mme Martin')


@pytest.fixture
def client_voisin(autre_entreprise):
    from apps.crm.models import Customer
    return Customer.objects.create(company=autre_entreprise,
                                   name='M. Dupont')


@pytest.fixture
def connecte(client, entreprise, django_user_model):
    user = django_user_model.objects.create_user(
        username='chef', password='motdepasse-test')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.save()
    client.force_login(user)
    return client


@pytest.fixture
def chantier(entreprise, client_crm):
    from apps.btp.models import BTPProject
    return BTPProject.objects.create(
        company=entreprise, name='Rénovation Martin', customer=client_crm,
        start_date=date(2026, 3, 2))


@pytest.fixture
def fichier():
    """Un fichier téléversé, nommé comme on veut.

    Le contenu n'a pas d'importance : Django ne valide le format d'un
    `ImageField` qu'au passage par un formulaire, et c'est précisément
    pourquoi un PDF peut se retrouver sous l'étiquette « Photo ».
    """
    from django.core.files.uploadedfile import SimpleUploadedFile

    def _poser(nom):
        return SimpleUploadedFile(nom, b'octets-de-test',
                                  content_type='application/octet-stream')
    return _poser


def _document(chantier, fichier, nom_du_fichier, doc_type='other',
              nom='Document'):
    from apps.btp.models import ProjectDocument
    return ProjectDocument.objects.create(
        project=chantier, name=nom, doc_type=doc_type,
        file=fichier(nom_du_fichier))


def _photo_de_reserve(chantier, fichier, titre='Fissure au plafond'):
    from apps.btp.models import ProjectReservation, ReservationPhoto
    reserve = ProjectReservation.objects.create(
        project=chantier, title=titre, description='À reprendre.')
    return ReservationPhoto.objects.create(
        reservation=reserve, photo=fichier('reserve.jpg'),
        caption='Angle nord')


def _photo_de_point(chantier, fichier, libelle='État de l\'existant'):
    from apps.btp.models import ProjectPlanStep, ProjectStepItem
    etape = ProjectPlanStep.objects.create(
        project=chantier, name='Visite technique',
        step_type='technical_visit', order=1)
    point = ProjectStepItem.objects.create(
        step=etape, label=libelle, answer_type='photo',
        answer_photo=fichier('point.jpg'))
    return etape, point


def _page(client, chantier, onglet=None):
    url = reverse('btp:project_detail', args=[chantier.pk])
    if onglet:
        url += '?tab=' + onglet
    reponse = client.get(url)
    assert reponse.status_code == 200
    return reponse


# ── Le bouton ───────────────────────────────────────────────────────────────

def test_l_onglet_photos_est_propose_a_cote_des_autres(connecte, chantier):
    """Le bouton demandé : dans la même barre que Informations et Étapes."""
    contenu = _page(connecte, chantier).content.decode()

    assert '?tab=photos' in contenu
    assert 'Photos (0)' in contenu

    # Et il est bien DANS la barre d'onglets, à côté des autres : posé
    # ailleurs dans la page, il remplirait la demande à la lettre et pas
    # du tout dans l'esprit.
    debut = contenu.index('erp-tabs')
    fin = contenu.index('</div>', contenu.index('tab=supplies'))
    barre = contenu[debut:fin]
    assert 'tab=photos' in barre
    assert 'Informations' in barre


def test_le_compteur_de_l_onglet_suit_les_photos(connecte, chantier, fichier):
    _document(chantier, fichier, 'facade.jpg')
    _photo_de_reserve(chantier, fichier)

    contenu = _page(connecte, chantier).content.decode()

    assert 'Photos (2)' in contenu


# ── C'est l'extension qui décide, pas l'étiquette ──────────────────────────

def test_un_document_image_apparait_dans_la_galerie(connecte, chantier,
                                                    fichier):
    document = _document(chantier, fichier, 'facade.jpg',
                         nom='Façade avant travaux')

    contenu = _page(connecte, chantier, 'photos').content.decode()

    assert 'Façade avant travaux' in contenu

    # L'URL DE SERVICE, et non celle du stockage.
    #
    # Deux versions de ce test ont eu tort avant celle-ci, et c'est
    # instructif. La première cherchait « facade.jpg » : faux, le stockage
    # de Django suffixe les homonymes. La seconde cherchait
    # `document.file.url`, c'est-à-dire /media/project_documents/… : faux
    # aussi, et cette fois le CODE avait tort — media_access.py refuse ce
    # préfixe, les vignettes s'affichaient donc cassées en production
    # pendant que le test passait au vert.
    attendue = reverse('btp:project_photo',
                       args=[chantier.pk, 'document', document.pk])
    assert '<img src="%s"' % attendue in contenu
    assert '/media/project_documents/' not in contenu


def test_un_pdf_etiquete_photo_n_apparait_pas(connecte, chantier, fichier):
    """Le cas qui afficherait une image cassée au milieu de la galerie."""
    _document(chantier, fichier, 'rapport.pdf', doc_type='photo',
              nom='Rapport scanné')

    contenu = _page(connecte, chantier, 'photos').content.decode()

    assert 'rapport.pdf' not in contenu
    assert 'Aucune photo sur ce chantier' in contenu


def test_une_image_etiquetee_autrement_apparait_quand_meme(connecte, chantier,
                                                           fichier):
    """Une photo de chantier est souvent déposée sous un autre type.

    « Rapport journalier », « Document client »… Juger l'étiquette la
    ferait disparaître de la galerie.
    """
    _document(chantier, fichier, 'chantier.png', doc_type='daily_report',
              nom='Avancement du 3 mars')

    contenu = _page(connecte, chantier, 'photos').content.decode()

    assert 'Avancement du 3 mars' in contenu


# ── Chaque vignette dit d'où elle vient ────────────────────────────────────

def test_une_photo_de_reserve_porte_son_origine(connecte, chantier, fichier):
    _photo_de_reserve(chantier, fichier, titre='Fissure au plafond')

    contenu = _page(connecte, chantier, 'photos').content.decode()

    assert 'Réserve' in contenu
    assert 'Fissure au plafond' in contenu


def test_une_photo_de_point_renvoie_vers_son_etape(connecte, chantier,
                                                   fichier):
    etape, _point = _photo_de_point(chantier, fichier)

    contenu = _page(connecte, chantier, 'photos').content.decode()

    assert 'Étape' in contenu
    assert reverse('btp:step_detail', args=[etape.pk]) in contenu


def test_les_trois_sources_cohabitent(connecte, chantier, fichier):
    _document(chantier, fichier, 'facade.jpg', nom='Façade')
    _photo_de_reserve(chantier, fichier)
    _photo_de_point(chantier, fichier)

    from apps.btp import services_photos
    origines = [p['origine']
                for p in services_photos.photos_du_chantier(chantier)]

    assert sorted(origines) == ['Document', 'Réserve', 'Étape']


# ── L'ordre ─────────────────────────────────────────────────────────────────

def test_les_plus_recentes_d_abord(chantier, fichier):
    from apps.btp import services_photos
    from apps.btp.models import ProjectDocument

    vieux = _document(chantier, fichier, 'vieille.jpg', nom='Vieille')
    recent = _document(chantier, fichier, 'recente.jpg', nom='Récente')
    # `added_at` est en auto_now_add : on le repositionne en base.
    ProjectDocument.objects.filter(pk=vieux.pk).update(
        added_at=timezone.now() - timedelta(days=10))
    ProjectDocument.objects.filter(pk=recent.pk).update(
        added_at=timezone.now())

    titres = [p['titre']
              for p in services_photos.photos_du_chantier(chantier)]

    assert titres == ['Récente', 'Vieille']


def test_une_photo_sans_date_passe_a_la_fin(chantier, fichier):
    """Un point de contrôle peut porter une photo sans être rempli.

    `filled_at` est alors nul. Elle doit figurer dans la galerie — c'est
    une vraie photo du chantier — mais après celles qu'on peut situer
    dans le temps.
    """
    from apps.btp import services_photos

    _photo_de_point(chantier, fichier, libelle='Sans date')
    _document(chantier, fichier, 'datee.jpg', nom='Datée')

    photos = services_photos.photos_du_chantier(chantier)

    assert [p['titre'] for p in photos] == ['Datée', 'Sans date']
    assert photos[-1]['date'] is None


# ── Isolement entre entreprises ────────────────────────────────────────────

def test_les_photos_d_une_autre_entreprise_ne_fuient_jamais(
        connecte, chantier, autre_entreprise, client_voisin, fichier):
    """Le test qui compte le plus. Ce module a déjà connu cette fuite."""
    from apps.btp.models import BTPProject

    chantier_voisin = BTPProject.objects.create(
        company=autre_entreprise, name='Chantier Ampere',
        customer=client_voisin, start_date=date(2026, 4, 1))
    _document(chantier_voisin, fichier, 'secret.jpg', nom='Plan confidentiel')
    _photo_de_reserve(chantier_voisin, fichier, titre='Réserve voisine')

    contenu = _page(connecte, chantier, 'photos').content.decode()

    assert 'Plan confidentiel' not in contenu
    assert 'Réserve voisine' not in contenu
    assert 'secret.jpg' not in contenu

    # Et la fiche du voisin reste inaccessible, onglet photos compris.
    reponse = connecte.get(
        reverse('btp:project_detail', args=[chantier_voisin.pk])
        + '?tab=photos')
    assert reponse.status_code == 404


def test_le_compteur_ignore_aussi_les_autres_entreprises(
        chantier, autre_entreprise, client_voisin, fichier):
    from apps.btp import services_photos
    from apps.btp.models import BTPProject

    voisin = BTPProject.objects.create(
        company=autre_entreprise, name='Chantier Ampere',
        customer=client_voisin, start_date=date(2026, 4, 1))
    _document(voisin, fichier, 'secret.jpg')
    _photo_de_reserve(voisin, fichier)
    _photo_de_point(voisin, fichier)

    assert services_photos.compter_les_photos(chantier) == 0
    assert services_photos.compter_les_photos(voisin) == 3


# ── Économie : la galerie n'est bâtie que si on l'ouvre ────────────────────

def test_la_galerie_n_est_pas_construite_hors_de_son_onglet(connecte,
                                                            chantier,
                                                            fichier):
    """La fiche d'un chantier se consulte bien plus souvent que ses photos.

    Le compteur, lui, est toujours calculé : c'est trois requêtes légères,
    et sans lui le bouton ne dirait pas combien de photos attendent.
    """
    _document(chantier, fichier, 'facade.jpg')

    reponse = _page(connecte, chantier)

    assert reponse.context['photos'] is None
    assert reponse.context['nb_photos'] == 1


def test_sur_son_onglet_la_galerie_est_bien_la(connecte, chantier, fichier):
    _document(chantier, fichier, 'facade.jpg')

    reponse = _page(connecte, chantier, 'photos')

    assert len(reponse.context['photos']) == 1


# ── Robustesse ──────────────────────────────────────────────────────────────

def test_le_compteur_et_la_galerie_disent_le_meme_nombre(chantier, fichier):
    """Deux chemins de calcul : ils doivent concorder.

    Le compteur passe par trois requêtes SQL, la galerie par un parcours
    des objets. S'ils divergent, le bouton annonce un nombre que l'écran
    ne montre pas.
    """
    from apps.btp import services_photos

    _document(chantier, fichier, 'a.jpg')
    _document(chantier, fichier, 'b.pdf', doc_type='photo')
    _photo_de_reserve(chantier, fichier)
    _photo_de_point(chantier, fichier)

    assert (services_photos.compter_les_photos(chantier)
            == len(services_photos.photos_du_chantier(chantier)) == 3)


def test_une_extension_inconnue_n_est_jamais_une_photo():
    from apps.btp import services_photos

    assert not services_photos.est_une_image('')
    assert not services_photos.est_une_image(None)
    assert not services_photos.est_une_image('notice.pdf')
    assert not services_photos.est_une_image('archive.zip')
    assert services_photos.est_une_image('photo.JPG')
    assert services_photos.est_une_image('dossier/vue.webp')


def test_sans_photo_la_page_explique_ou_elles_arrivent(connecte, chantier):
    """Un écran vide doit dire quoi faire, pas seulement qu'il est vide.

    La galerie n'a pas de bouton de dépôt, et c'est voulu : une photo
    appartient à un document, à une réserve ou à un point de contrôle, et
    la déposer hors de ce contexte lui ferait perdre son sens.
    """
    contenu = _page(connecte, chantier, 'photos').content.decode()

    assert 'Aucune photo sur ce chantier' in contenu
    assert 'réserve' in contenu
    assert 'point de contrôle' in contenu
