# -*- coding: utf-8 -*-
"""Qui peut voir une photo de chantier, et par quel chemin elle est servie.

DÉFAUT RAPPORTÉ LE 09/11/2026, capture d'écran à l'appui. La galerie
s'affichait correctement — titres, origines, dates — mais **toutes** les
vignettes marquées « Document » étaient cassées.

`apps/core/media_access.py` applique un refus par défaut sous `/media/` et
ne sert que des préfixes nommés. `reservations/` en fait partie ;
`project_documents/` et `btp/checklists/` non, délibérément, puisqu'on y
trouve devis, contrats et documents clients. Seules les photos de réserves
s'affichaient donc — ce qui collait exactement à la capture.

LA CORRECTION FACILE AURAIT ÉTÉ UNE FUITE. Ajouter ces deux préfixes à la
liste blanche aurait suffi à réparer l'affichage, et aurait rendu les
documents de chaque chantier lisibles par n'importe quel utilisateur
connecté de n'importe quelle autre société : cette liste ne connaît pas la
notion d'entreprise.

Les photos passent donc par une vue qui vérifie l'entreprise à chaque
lecture. Ce fichier tient cette vérification.
"""

import os
from datetime import date

import pytest
from django.urls import reverse

from tests.test_chantier_photos import (  # noqa: F401  (fixtures pytest)
    _document, _page, _photo_de_point, _photo_de_reserve, autre_entreprise,
    chantier, client_crm, client_voisin, connecte, entreprise, fichier)

pytestmark = pytest.mark.django_db


def _url(chantier, origine, pk):
    return reverse('btp:project_photo', args=[chantier.pk, origine, pk])


# ─── Le garde-fou contre le retour du défaut ──────────────────────────────

def test_la_galerie_n_expose_jamais_une_url_media_interdite(connecte,
                                                            chantier,
                                                            fichier):
    """Les deux préfixes que media_access refuse ne doivent plus paraître."""
    _document(chantier, fichier, 'facade.jpg')
    _photo_de_point(chantier, fichier)

    contenu = _page(connecte, chantier, 'photos').content.decode()

    assert '/media/project_documents/' not in contenu, (
        'prefixe refuse par media_access : la vignette serait cassee')
    assert '/media/btp/checklists/' not in contenu


def test_les_trois_origines_sont_reellement_servies(connecte, chantier,
                                                    fichier):
    """Le test qui aurait attrapé le défaut d'origine.

    Les anciens tests vérifiaient que la galerie CONTENAIT une URL. Aucun
    ne vérifiait que cette URL RÉPONDAIT. C'est tout l'écart entre un test
    vert et une page qui marche.
    """
    from apps.btp import services_photos

    _document(chantier, fichier, 'facade.jpg')
    _photo_de_reserve(chantier, fichier)
    _photo_de_point(chantier, fichier)

    photos = services_photos.photos_du_chantier(chantier)
    assert len(photos) == 3

    for photo in photos:
        reponse = connecte.get(photo['url'])
        assert reponse.status_code == 200, (
            'origine non servie : %s (%s)' % (photo['origine'], photo['url']))


# ─── Ce que la vue rend ────────────────────────────────────────────────────

def test_la_vue_sert_bien_le_fichier(connecte, chantier, fichier):
    document = _document(chantier, fichier, 'facade.jpg')

    reponse = connecte.get(_url(chantier, 'document', document.pk))

    assert reponse.status_code == 200
    assert reponse['Content-Type'] == 'image/jpeg'
    assert b''.join(reponse.streaming_content) == b'octets-de-test'


def test_la_vue_interdit_tout_cache_partage(connecte, chantier, fichier):
    """Ces images appartiennent à UNE entreprise.

    Un cache intermédiaire qui les redistribuerait annulerait la
    vérification faite à chaque lecture.

    Ce test a d'abord exigé « private », et il avait tort : le middleware
    d'apps/core impose « no-store » à toute réponse servie à un utilisateur
    connecté, ce qui est PLUS strict. Il vérifie donc la propriété qui
    compte — jamais de cache partagé — plutôt qu'une formulation
    particulière.
    """
    document = _document(chantier, fichier, 'facade.jpg')

    reponse = connecte.get(_url(chantier, 'document', document.pk))
    cache = reponse.get('Cache-Control', '')

    assert 'public' not in cache, cache
    assert 'no-store' in cache or 'private' in cache, cache


# ─── Isolement : la raison d'être de cette vue ────────────────────────────

def test_la_photo_d_une_autre_entreprise_est_refusee(
        connecte, chantier, autre_entreprise, client_voisin, fichier):
    from apps.btp.models import BTPProject

    voisin = BTPProject.objects.create(
        company=autre_entreprise, name='Chantier Ampere',
        customer=client_voisin, start_date=date(2026, 4, 1))
    secret = _document(voisin, fichier, 'secret.jpg')

    # Par le chantier du voisin : il n'appartient pas a cette entreprise.
    assert connecte.get(
        _url(voisin, 'document', secret.pk)).status_code == 404

    # Et en maquillant l'URL avec SON propre chantier : la photo n'y est pas.
    assert connecte.get(
        _url(chantier, 'document', secret.pk)).status_code == 404


def test_une_photo_d_un_autre_chantier_est_refusee(connecte, chantier,
                                                   entreprise, client_crm,
                                                   fichier):
    """Même entreprise, mais pas le bon chantier.

    L'URL porte deux identifiants, et c'est leur LIEN qui est vérifié, pas
    chacun de son côté. Sans cela, connaître un identifiant de document
    suffirait à le lire depuis n'importe quel chantier.
    """
    from apps.btp.models import BTPProject

    second = BTPProject.objects.create(
        company=entreprise, name='Autre chantier', customer=client_crm,
        start_date=date(2026, 5, 1))
    ailleurs = _document(second, fichier, 'ailleurs.jpg')

    reponse = connecte.get(_url(chantier, 'document', ailleurs.pk))

    assert reponse.status_code == 404


def test_un_visiteur_anonyme_ne_voit_aucune_photo(client, chantier, fichier):
    document = _document(chantier, fichier, 'facade.jpg')

    reponse = client.get(_url(chantier, 'document', document.pk))

    assert reponse.status_code in (302, 403), (
        'une photo de chantier ne doit jamais etre lisible sans compte')


# ─── Robustesse ────────────────────────────────────────────────────────────

def test_une_origine_inconnue_est_refusee(connecte, chantier, fichier):
    document = _document(chantier, fichier, 'facade.jpg')

    reponse = connecte.get(_url(chantier, 'inconnue', document.pk))

    assert reponse.status_code == 404


def test_un_fichier_disparu_du_disque_rend_404_et_non_500(connecte, chantier,
                                                          fichier):
    """Une sauvegarde restaurée sans les médias, un déplacement à la main.

    C'est une image manquante, pas une panne de l'ERP — et une erreur 500
    sur une vignette ferait croire à une panne générale.
    """
    document = _document(chantier, fichier, 'facade.jpg')
    os.remove(document.file.path)

    reponse = connecte.get(_url(chantier, 'document', document.pk))

    assert reponse.status_code == 404
