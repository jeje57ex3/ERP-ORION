# -*- coding: utf-8 -*-
"""Une photo retirée d'un chantier reste récupérable deux semaines.

POURQUOI UNE CORBEILLE PLUTÔT QU'UNE SUPPRESSION. Une photo de chantier
peut servir de preuve en cas de litige, et un clic de trop ne doit pas la
faire disparaître à jamais. Elle est donc datée, retirée de la galerie, et
détruite pour de bon quatorze jours plus tard.

TROIS CHOSES QUE CES TESTS TIENNENT, et dont chacune a été écrite parce
qu'elle pouvait silencieusement mal tourner.

1. **Ce qui entoure la photo survit.** Une réserve est une malfaçon
   signalée : elle reste à traiter sans son image. Un point de contrôle est
   une question : il reste, et redevient « non renseigné » — donc compté
   par l'avertisseur de l'onglet Étapes. Seul un document s'en va avec sa
   photo, parce qu'il EST la photo.

2. **Le client ne doit plus la voir.** Un document mis à la corbeille
   disparaît aussi du portail client, liste et téléchargement compris.
   Sans ce filtre, une photo « supprimée » resterait visible et
   téléchargeable par le client pendant quinze jours.

3. **La purge arrive vraiment.** Elle tourne à l'ouverture de l'écran ET
   dans une tâche périodique. Ce dépôt a déjà livré trois choses que rien
   n'activait ; une purge qui ne tourne jamais afficherait « 0 jour
   restant » sur des fichiers toujours présents.
"""

import os
from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.test_chantier_photos import (  # noqa: F401  (fixtures pytest)
    _document, _page, _photo_de_point, _photo_de_reserve, autre_entreprise,
    chantier, client_crm, client_voisin, connecte, entreprise, fichier)

pytestmark = pytest.mark.django_db


def _url_corbeille(chantier, origine, pk):
    return reverse('btp:project_photo_delete',
                   args=[chantier.pk, origine, pk])


def _url_restauration(chantier, origine, pk):
    return reverse('btp:project_photo_restore',
                   args=[chantier.pk, origine, pk])


def _vieillir(objet, champ, jours):
    """Recule la date de mise à la corbeille, pour tester la purge."""
    type(objet).objects.filter(pk=objet.pk).update(
        **{champ: timezone.now() - timedelta(days=jours)})


# ─── Mettre à la corbeille ne détruit rien ────────────────────────────────

def test_la_photo_quitte_la_galerie_mais_pas_le_disque(connecte, chantier,
                                                       fichier):
    from apps.btp import services_photos
    from apps.btp.models import ProjectDocument

    document = _document(chantier, fichier, 'facade.jpg')
    chemin = document.file.path

    connecte.post(_url_corbeille(chantier, 'document', document.pk))

    assert services_photos.photos_du_chantier(chantier) == []
    assert services_photos.compter_les_photos(chantier) == 0
    assert ProjectDocument.objects.filter(pk=document.pk).exists(), (
        'la ligne a ete detruite : il n-y a plus rien a restaurer')
    assert os.path.exists(chemin), (
        'le fichier a ete detruit : la corbeille ne sert a rien')


def test_elle_apparait_dans_la_corbeille_avec_son_delai(connecte, chantier,
                                                        fichier):
    from apps.btp import services_photos

    document = _document(chantier, fichier, 'facade.jpg')
    connecte.post(_url_corbeille(chantier, 'document', document.pk))

    corbeille = services_photos.photos_du_chantier(chantier, corbeille=True)

    assert len(corbeille) == 1
    assert corbeille[0]['jours_restants'] == 14
    assert 'restauration' in corbeille[0]


def test_la_reserve_survit_a_la_perte_de_sa_photo(connecte, chantier,
                                                  fichier):
    """Une malfaçon signalée reste à traiter sans son image."""
    from apps.btp.models import ProjectReservation

    cliche = _photo_de_reserve(chantier, fichier, titre='Fissure au plafond')
    reserve = cliche.reservation

    connecte.post(_url_corbeille(chantier, 'reserve', cliche.pk))

    assert ProjectReservation.objects.filter(pk=reserve.pk).exists()
    cliche.refresh_from_db()
    assert cliche.corbeille_le is not None


def test_un_point_redevient_non_renseigne(connecte, chantier, fichier):
    """LE test qui compte pour les étapes.

    Sans cela, retirer une photo laisserait le point compté comme rempli
    alors qu'il ne l'est plus — et l'oubli dormirait jusqu'à la réception
    du chantier.
    """
    from apps.btp import services_etapes
    from apps.btp.models import ProjectStepItem

    _etape, point = _photo_de_point(chantier, fichier)
    point.is_required = True
    point.save(update_fields=['is_required'])
    assert point.is_answered

    connecte.post(_url_corbeille(chantier, 'point', point.pk))

    point.refresh_from_db()
    assert ProjectStepItem.objects.filter(pk=point.pk).exists()
    assert point.label, 'la question a ete perdue'
    assert point.answer_photo, 'la photo doit rester, elle est restaurable'
    assert not point.is_answered, (
        'le point reste compte comme rempli alors que sa photo est a la '
        'corbeille')
    assert services_etapes.compter_les_points_manquants(chantier) >= 1


# ─── Le client ne la voit plus ────────────────────────────────────────────

def test_un_document_a_la_corbeille_disparait_du_portail_client(
        connecte, chantier, fichier, django_user_model, client, entreprise):
    """Sans ce filtre, le client verrait et téléchargerait quinze jours
    durant une photo que l'entreprise croit supprimée."""
    from apps.crm.models import Customer
    from apps.portals.models import ClientPortalAccount

    courriel = 'martin@exemple.fr'
    chantier.customer.email = courriel
    chantier.customer.save(update_fields=['email'])
    Customer.objects.filter(pk=chantier.customer.pk).update(email=courriel)

    utilisateur = django_user_model.objects.create_user(
        username=courriel, email=courriel, password='motdepasse-test')
    ClientPortalAccount.objects.create(
        company=entreprise, user=utilisateur, email=courriel,
        first_name='Paul', last_name='Martin')

    # Un nom DISTINCTIF, et c'est le détail qui rendait ce test faux.
    # Appelé « Document », il se retrouvait dans le titre de la page
    # (« Documents — Orion ERP ») : l'assertion passait au vert avant la
    # mise à la corbeille comme après, sans rien prouver du tout.
    document = _document(chantier, fichier, 'facade.jpg',
                         nom='Fissure-poutre-nord-42')
    document.visible_to_client = True
    document.save(update_fields=['visible_to_client'])

    navigateur = client.__class__()
    navigateur.force_login(utilisateur)
    url_liste = reverse('client_portal:project_documents',
                        args=[chantier.pk])
    url_telechargement = reverse(
        'client_portal:project_document_download',
        args=[chantier.pk, document.pk])

    assert document.name in navigateur.get(url_liste).content.decode()
    assert navigateur.get(url_telechargement).status_code == 200

    connecte.post(_url_corbeille(chantier, 'document', document.pk))

    assert document.name not in navigateur.get(url_liste).content.decode()
    assert navigateur.get(url_telechargement).status_code == 404


# ─── Restaurer ────────────────────────────────────────────────────────────

def test_restaurer_remet_la_photo_dans_la_galerie(connecte, chantier,
                                                  fichier):
    from apps.btp import services_photos

    document = _document(chantier, fichier, 'facade.jpg')
    connecte.post(_url_corbeille(chantier, 'document', document.pk))

    connecte.post(_url_restauration(chantier, 'document', document.pk))

    assert len(services_photos.photos_du_chantier(chantier)) == 1
    assert services_photos.photos_du_chantier(chantier, corbeille=True) == []


def test_restaurer_un_point_le_rend_a_nouveau_renseigne(connecte, chantier,
                                                        fichier):
    _etape, point = _photo_de_point(chantier, fichier)
    connecte.post(_url_corbeille(chantier, 'point', point.pk))

    connecte.post(_url_restauration(chantier, 'point', point.pk))

    point.refresh_from_db()
    assert point.is_answered


def test_restaurer_ce_qui_n_est_pas_a_la_corbeille_ne_fait_rien(
        connecte, chantier, fichier):
    document = _document(chantier, fichier, 'facade.jpg')

    reponse = connecte.post(
        _url_restauration(chantier, 'document', document.pk))

    assert reponse.status_code == 302
    document.refresh_from_db()
    assert document.corbeille_le is None


# ─── La purge, quatorze jours plus tard ───────────────────────────────────

def test_rien_n_est_purge_avant_le_delai(connecte, chantier, fichier):
    from apps.btp import services_photos
    from apps.btp.models import ProjectDocument

    document = _document(chantier, fichier, 'facade.jpg')
    connecte.post(_url_corbeille(chantier, 'document', document.pk))
    document.refresh_from_db()
    _vieillir(document, 'corbeille_le', 13)

    services_photos.purger_la_corbeille()

    assert ProjectDocument.objects.filter(pk=document.pk).exists()


def test_apres_le_delai_le_document_et_son_fichier_partent(connecte,
                                                           chantier,
                                                           fichier):
    from apps.btp import services_photos
    from apps.btp.models import ProjectDocument

    document = _document(chantier, fichier, 'facade.jpg')
    chemin = document.file.path
    connecte.post(_url_corbeille(chantier, 'document', document.pk))
    document.refresh_from_db()
    _vieillir(document, 'corbeille_le', 15)

    comptes = services_photos.purger_la_corbeille()

    assert comptes['documents'] == 1
    assert not ProjectDocument.objects.filter(pk=document.pk).exists()
    assert not os.path.exists(chemin), (
        'le fichier reste sur le disque : un orphelin de plus')


def test_la_purge_garde_le_point_et_ne_retire_que_sa_photo(connecte,
                                                           chantier,
                                                           fichier):
    """Même après quatorze jours, la question reste à poser."""
    from apps.btp import services_photos
    from apps.btp.models import ProjectStepItem

    _etape, point = _photo_de_point(chantier, fichier)
    chemin = point.answer_photo.path
    connecte.post(_url_corbeille(chantier, 'point', point.pk))
    point.refresh_from_db()
    _vieillir(point, 'photo_corbeille_le', 15)

    comptes = services_photos.purger_la_corbeille()

    assert comptes['points'] == 1
    point.refresh_from_db()
    assert ProjectStepItem.objects.filter(pk=point.pk).exists()
    assert not point.answer_photo
    assert point.photo_corbeille_le is None, (
        'le point reste marque comme ayant une photo a la corbeille alors '
        "qu'il n-en a plus du tout")
    assert not os.path.exists(chemin)


def test_la_purge_garde_la_reserve(connecte, chantier, fichier):
    from apps.btp import services_photos
    from apps.btp.models import ProjectReservation, ReservationPhoto

    cliche = _photo_de_reserve(chantier, fichier)
    reserve = cliche.reservation
    connecte.post(_url_corbeille(chantier, 'reserve', cliche.pk))
    cliche.refresh_from_db()
    _vieillir(cliche, 'corbeille_le', 15)

    services_photos.purger_la_corbeille()

    assert not ReservationPhoto.objects.filter(pk=cliche.pk).exists()
    assert ProjectReservation.objects.filter(pk=reserve.pk).exists()


def test_ouvrir_la_corbeille_purge_ce_qui_est_echu(connecte, chantier,
                                                   fichier):
    """La promesse ne doit pas dépendre d'un planificateur non configuré."""
    from apps.btp.models import ProjectDocument

    document = _document(chantier, fichier, 'facade.jpg')
    connecte.post(_url_corbeille(chantier, 'document', document.pk))
    document.refresh_from_db()
    _vieillir(document, 'corbeille_le', 20)

    _page(connecte, chantier, 'corbeille')

    assert not ProjectDocument.objects.filter(pk=document.pk).exists()


def test_la_tache_periodique_appelle_la_meme_purge():
    """Les deux chemins doivent faire exactement la même chose."""
    from apps.btp import tasks

    assert tasks.purger_la_corbeille_photos.name == (
        'btp.purger_la_corbeille_photos')
    assert tasks.purger_la_corbeille_photos() == {
        'documents': 0, 'reserves': 0, 'points': 0}


def test_le_decompte_des_jours_est_juste():
    from apps.btp import services_photos

    maintenant = timezone.now()
    assert services_photos.jours_restants(None) is None
    assert services_photos.jours_restants(maintenant) == 14
    assert services_photos.jours_restants(
        maintenant - timedelta(days=13)) == 1
    assert services_photos.jours_restants(
        maintenant - timedelta(days=30)) == 0, (
        'un delai depasse ne doit jamais afficher un nombre negatif')


# ─── Ce qui reste refusé ──────────────────────────────────────────────────

def test_la_mise_a_la_corbeille_exige_un_post(connecte, chantier, fichier):
    """Un lien visité ne doit jamais retirer quoi que ce soit."""
    document = _document(chantier, fichier, 'facade.jpg')

    assert connecte.get(
        _url_corbeille(chantier, 'document', document.pk)).status_code == 405
    document.refresh_from_db()
    assert document.corbeille_le is None


def test_la_restauration_exige_un_post(connecte, chantier, fichier):
    document = _document(chantier, fichier, 'facade.jpg')
    connecte.post(_url_corbeille(chantier, 'document', document.pk))

    assert connecte.get(
        _url_restauration(chantier, 'document',
                          document.pk)).status_code == 405


def test_on_ne_touche_pas_a_la_photo_d_une_autre_entreprise(
        connecte, chantier, autre_entreprise, client_voisin, fichier):
    from apps.btp.models import BTPProject

    voisin = BTPProject.objects.create(
        company=autre_entreprise, name='Chantier Ampere',
        customer=client_voisin, start_date=date(2026, 4, 1))
    secret = _document(voisin, fichier, 'secret.jpg')

    assert connecte.post(
        _url_corbeille(voisin, 'document', secret.pk)).status_code == 404
    connecte.post(_url_corbeille(chantier, 'document', secret.pk))

    secret.refresh_from_db()
    assert secret.corbeille_le is None


def test_la_vignette_d_une_photo_a_la_corbeille_reste_visible(connecte,
                                                              chantier,
                                                              fichier):
    """On ne restaure pas de confiance une photo qu'on ne voit pas."""
    document = _document(chantier, fichier, 'facade.jpg')
    connecte.post(_url_corbeille(chantier, 'document', document.pk))

    reponse = connecte.get(reverse(
        'btp:project_photo', args=[chantier.pk, 'document', document.pk]))

    assert reponse.status_code == 200


def test_l_onglet_corbeille_n_apparait_que_s_il_y_a_quelque_chose(
        connecte, chantier, fichier):
    document = _document(chantier, fichier, 'facade.jpg')

    assert 'tab=corbeille' not in _page(connecte, chantier).content.decode()

    connecte.post(_url_corbeille(chantier, 'document', document.pk))

    assert 'tab=corbeille' in _page(connecte, chantier).content.decode()
