# -*- coding: utf-8 -*-
"""Retirer une photo d'un chantier, sans détruire ce qui l'entoure.

LE PIÈGE DE CETTE FONCTIONNALITÉ. « Supprimer la photo » ne veut pas dire
la même chose selon d'où elle vient, et traiter les trois cas de la même
façon détruirait des données qui n'ont rien à voir avec l'image :

* **document** — le document EST la photo : il part.
* **réserve** — seule la photo part. Le titre, la description et le statut
  sont le dossier ; supprimer la réserve avec son image ferait disparaître
  une malfaçon signalée.
* **point de contrôle** — seule la RÉPONSE est effacée. La question reste,
  et le point redevient « non renseigné », donc compté par l'avertisseur de
  l'onglet Étapes. Supprimer le point ferait disparaître du contrôle une
  case qu'il faut encore remplir.

Ces trois distinctions sont le cœur de ce fichier.
"""

import os
from datetime import date

import pytest
from django.urls import reverse

from tests.test_chantier_photos import (  # noqa: F401  (fixtures pytest)
    _document, _page, _photo_de_point, _photo_de_reserve, autre_entreprise,
    chantier, client_crm, client_voisin, connecte, entreprise, fichier)

pytestmark = pytest.mark.django_db


def _url_suppression(chantier, origine, pk):
    return reverse('btp:project_photo_delete',
                   args=[chantier.pk, origine, pk])


# ─── Ce que « supprimer » fait, origine par origine ───────────────────────

def test_un_document_photo_est_supprime(connecte, chantier, fichier):
    from apps.btp.models import ProjectDocument

    document = _document(chantier, fichier, 'facade.jpg')
    chemin = document.file.path

    reponse = connecte.post(
        _url_suppression(chantier, 'document', document.pk))

    assert reponse.status_code == 302
    assert not ProjectDocument.objects.filter(pk=document.pk).exists()
    assert not os.path.exists(chemin), (
        'le fichier reste sur le disque : un orphelin que plus rien ne '
        'reference et que personne ne retrouvera')


def test_supprimer_la_photo_d_une_reserve_garde_la_reserve(connecte,
                                                           chantier,
                                                           fichier):
    """Une réserve sans sa photo reste une malfaçon à traiter."""
    from apps.btp.models import ProjectReservation, ReservationPhoto

    cliche = _photo_de_reserve(chantier, fichier, titre='Fissure au plafond')
    reserve = cliche.reservation

    connecte.post(_url_suppression(chantier, 'reserve', cliche.pk))

    assert not ReservationPhoto.objects.filter(pk=cliche.pk).exists()
    assert ProjectReservation.objects.filter(pk=reserve.pk).exists(), (
        'la reserve a disparu avec sa photo : une malfaçon signalee '
        'vient d-etre effacee')


def test_supprimer_la_photo_d_un_point_garde_la_question(connecte, chantier,
                                                         fichier):
    """Le point redevient « non renseigné », donc signalé.

    Supprimer le point lui-même ferait disparaître du contrôle une case
    qu'il reste à remplir — et personne ne saurait qu'elle manque.
    """
    from apps.btp.models import ProjectStepItem

    _etape, point = _photo_de_point(chantier, fichier)

    connecte.post(_url_suppression(chantier, 'point', point.pk))

    point.refresh_from_db()
    assert ProjectStepItem.objects.filter(pk=point.pk).exists()
    assert not point.answer_photo
    assert point.label, 'la question a ete perdue'


def test_la_photo_disparait_bien_de_la_galerie(connecte, chantier, fichier):
    from apps.btp import services_photos

    document = _document(chantier, fichier, 'facade.jpg')
    assert len(services_photos.photos_du_chantier(chantier)) == 1

    connecte.post(_url_suppression(chantier, 'document', document.pk))

    assert services_photos.photos_du_chantier(chantier) == []
    assert services_photos.compter_les_photos(chantier) == 0


# ─── Ce que la suppression refuse ─────────────────────────────────────────

def test_la_suppression_exige_un_post(connecte, chantier, fichier):
    """Un lien visité ne doit jamais détruire quoi que ce soit.

    Un préchargement de navigateur ou un robot d'indexation suffirait à
    vider la galerie.
    """
    from apps.btp.models import ProjectDocument

    document = _document(chantier, fichier, 'facade.jpg')

    reponse = connecte.get(
        _url_suppression(chantier, 'document', document.pk))

    assert reponse.status_code == 405
    assert ProjectDocument.objects.filter(pk=document.pk).exists()


def test_on_ne_supprime_pas_la_photo_d_une_autre_entreprise(
        connecte, chantier, autre_entreprise, client_voisin, fichier):
    from apps.btp.models import BTPProject, ProjectDocument

    voisin = BTPProject.objects.create(
        company=autre_entreprise, name='Chantier Ampere',
        customer=client_voisin, start_date=date(2026, 4, 1))
    secret = _document(voisin, fichier, 'secret.jpg')

    # Par le chantier du voisin.
    assert connecte.post(
        _url_suppression(voisin, 'document', secret.pk)).status_code == 404
    # Et en maquillant l'URL avec son propre chantier.
    connecte.post(_url_suppression(chantier, 'document', secret.pk))

    assert ProjectDocument.objects.filter(pk=secret.pk).exists(), (
        'un document d-une autre entreprise vient d-etre supprime')


def test_on_ne_supprime_pas_la_photo_d_un_autre_chantier(connecte, chantier,
                                                         entreprise,
                                                         client_crm,
                                                         fichier):
    """Même entreprise, mais l'URL porte deux identifiants liés."""
    from apps.btp.models import BTPProject, ProjectDocument

    second = BTPProject.objects.create(
        company=entreprise, name='Autre chantier', customer=client_crm,
        start_date=date(2026, 5, 1))
    ailleurs = _document(second, fichier, 'ailleurs.jpg')

    connecte.post(_url_suppression(chantier, 'document', ailleurs.pk))

    assert ProjectDocument.objects.filter(pk=ailleurs.pk).exists()


def test_une_origine_inconnue_ne_supprime_rien(connecte, chantier, fichier):
    from apps.btp.models import ProjectDocument

    document = _document(chantier, fichier, 'facade.jpg')

    reponse = connecte.post(
        _url_suppression(chantier, 'inventee', document.pk))

    assert reponse.status_code == 302
    assert ProjectDocument.objects.filter(pk=document.pk).exists()


def test_supprimer_deux_fois_ne_leve_pas(connecte, chantier, fichier):
    """Un double clic, un retour arrière, un bouton réappuyé."""
    document = _document(chantier, fichier, 'facade.jpg')
    url = _url_suppression(chantier, 'document', document.pk)

    assert connecte.post(url).status_code == 302
    assert connecte.post(url).status_code == 302


def test_un_fichier_deja_disparu_n_empeche_pas_la_suppression(connecte,
                                                              chantier,
                                                              fichier):
    """La ligne doit partir même si le fichier manque déjà.

    Une sauvegarde restaurée sans les médias laisse exactement cet état.
    Lever ici rendrait une erreur 500 sur une suppression légitime.
    """
    from apps.btp.models import ProjectDocument

    document = _document(chantier, fichier, 'facade.jpg')
    os.remove(document.file.path)

    reponse = connecte.post(
        _url_suppression(chantier, 'document', document.pk))

    assert reponse.status_code == 302
    assert not ProjectDocument.objects.filter(pk=document.pk).exists()


# ─── Le bouton sur l'écran ────────────────────────────────────────────────

def test_chaque_vignette_porte_son_bouton(connecte, chantier, fichier):
    _document(chantier, fichier, 'facade.jpg')
    _photo_de_reserve(chantier, fichier)
    _photo_de_point(chantier, fichier)

    contenu = _page(connecte, chantier, 'photos').content.decode()

    from apps.btp import services_photos
    for photo in services_photos.photos_du_chantier(chantier):
        assert photo['suppression'] in contenu, (
            'pas de bouton pour %s' % photo['origine'])


def test_le_bouton_est_un_post_et_demande_confirmation(connecte, chantier,
                                                       fichier):
    """Une suppression ne part pas d'une URL visitée, et elle se confirme."""
    _document(chantier, fichier, 'facade.jpg')

    contenu = _page(connecte, chantier, 'photos').content.decode()

    assert 'method="post" action="/btp/chantiers/' in contenu
    assert 'onsubmit="return confirm(' in contenu
    assert 'csrfmiddlewaretoken' in contenu
